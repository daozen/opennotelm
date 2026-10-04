import asyncio
import base64
import hashlib
import json
from io import BytesIO

import httpx
import pytest
from image_factory import image_bytes, image_response
from opennotelm.errors import AppError
from opennotelm.image_adapter import OpenAIImagesAdapter, validated_image
from opennotelm.schemas import ModelInput
from PIL import Image
from restart_support import restart
from test_decks import create_deck, notebook_with_source
from test_decks import decks as deck_fixture
from test_models import config
from test_sources import wait_for_job


@pytest.fixture
def decks(settings):
    yield from deck_fixture.__wrapped__(settings)


def run_adapter(handler):
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await OpenAIImagesAdapter(client).generate(
                ModelInput(base_url="https://images.example/v1", model_id="custom-model"),
                "private-provider-key",
                "A visual metaphor.",
            )

    return asyncio.run(run())


def test_image_adapter_decodes_actual_pixels_preserves_alpha_and_sanitizes_metadata():
    def handler(request):
        assert request.headers["authorization"] == "Bearer private-provider-key"
        assert json.loads(request.content) == {
            "model": "custom-model",
            "prompt": "A visual metaphor.",
            "n": 1,
        }
        return httpx.Response(200, json=image_response())

    output = run_adapter(handler)
    assert (output.width, output.height) == (512, 512)
    with Image.open(BytesIO(output.data)) as image:
        assert image.format == "PNG"
    raw = BytesIO()
    image = Image.new("RGBA", (20, 20), (1, 2, 3, 40))
    image.save(raw, "PNG")
    cleaned = validated_image(raw.getvalue())
    with Image.open(BytesIO(cleaned.data)) as image:
        assert image.getpixel((0, 0)) == (1, 2, 3, 40)
        assert not image.info


@pytest.mark.parametrize(
    "item",
    [
        {"b64_json": "invalid!!!"},
        {"b64_json": base64.b64encode(b"not an image").decode()},
        {"url": "file:///etc/passwd"},
        {},
    ],
)
def test_invalid_image_responses_never_pass_capability_test(item):
    with pytest.raises(AppError):
        run_adapter(lambda request: httpx.Response(200, json={"data": [item]}))


def test_download_follows_validated_redirects_without_forwarding_credentials(monkeypatch):
    monkeypatch.setattr(
        "opennotelm.image_adapter.socket.getaddrinfo",
        lambda *args: [(2, 1, 6, "", ("93.184.216.34", 443))],
    )
    requests = []

    def handler(request):
        requests.append(request)
        if request.method == "POST":
            return httpx.Response(
                200,
                headers={"set-cookie": "secret-cookie=private; Path=/"},
                json={"data": [{"url": "https://images.example/asset"}]},
            )
        assert "authorization" not in request.headers and "cookie" not in request.headers
        if request.url.host == "images.example":
            return httpx.Response(
                302, headers={"location": "https://cdn.example/image.png?signature=secret"}
            )
        assert request.url.host == "93.184.216.34" and request.headers["host"] == "cdn.example"
        assert request.extensions["sni_hostname"] == "cdn.example"
        return httpx.Response(200, content=image_bytes())

    assert run_adapter(handler).width == 512
    assert len(requests) == 3


def test_url_download_rejects_private_dns_redirect_and_oversized_body(monkeypatch):
    monkeypatch.setattr(
        "opennotelm.image_adapter.socket.getaddrinfo",
        lambda *args: [(2, 1, 6, "", ("127.0.0.1", 443))],
    )
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"data": [{"url": "https://internal.example/private"}]})

    with pytest.raises(AppError, match="IMAGE_URL_REJECTED"):
        run_adapter(handler)
    assert len(calls) == 1
    monkeypatch.setattr("opennotelm.image_adapter.MAX_RESPONSE_BYTES", 20)
    with pytest.raises(AppError, match="IMAGE_OUTPUT_TOO_LARGE"):
        run_adapter(lambda request: httpx.Response(200, content=b"x" * 100))


class CapturingComposition:
    def __init__(self, db):
        self.db, self.calls = db, []

    async def render_slide(self, deck, slide, assets):
        self.calls.append((slide["id"], set(assets)))
        with self.db.connect() as conn:
            conn.execute(
                "UPDATE slides SET status='rendered',error_code=NULL,error_message=NULL WHERE id=?",
                (slide["id"],),
            )


def image_pipeline(client, state):
    assert client.post("/api/settings/models/test", json=config("image")).status_code == 200
    state["image_calls"] = 0
    client.app.state.decks.assets = client.app.state.assets
    composition = CapturingComposition(client.app.state.db)
    client.app.state.decks.composition = composition
    return composition


def test_saved_v2_assets_remain_visible_and_retry_does_not_upgrade_their_signature(decks):
    client, state, _ = decks
    image_pipeline(client, state)
    notebook, _ = notebook_with_source(client)
    deck, _ = create_deck(client, notebook)
    with client.app.state.db.connect() as conn:
        conn.execute(
            "UPDATE decks SET generation_metadata_json=? WHERE id=?",
            (json.dumps({"generation_version": "deck-content-v2"}), deck["id"]),
        )
        for slide in deck["slides"]:
            old = dict(slide["spec"])
            old.pop("visual_relationships")
            conn.execute("UPDATE slides SET spec_json=? WHERE id=?", (json.dumps(old), slide["id"]))
            for request in old["asset_requests"]:
                signature = {
                    "spec": old,
                    "style": deck["style"],
                    "request": request,
                    "version": "slide-image-v2",
                }
                digest = hashlib.sha256(json.dumps(signature, sort_keys=True).encode()).hexdigest()
                conn.execute(
                    "UPDATE assets SET input_hash=? WHERE slide_id=? AND request_id=?",
                    (digest, slide["id"], request["id"]),
                )
    restored = client.get(f"/api/decks/{deck['id']}").json()
    assert len(restored["slides"][1]["assets"]) == 1
    assert restored["slides"][1]["assets"][0]["status"] == "ready"
    before = state["image_calls"]
    slide = restored["slides"][1]
    with client.app.state.db.connect() as conn:
        conn.execute("UPDATE slides SET status='failed' WHERE id=?", (slide["id"],))
        conn.execute("UPDATE decks SET status='partial' WHERE id=?", (deck["id"],))
    response = client.post(f"/api/decks/{deck['id']}/slides/{slide['id']}/retry")
    assert response.status_code == 202
    assert wait_for_job(client, response.json()["id"])["status"] == "completed"
    restored = client.get(f"/api/decks/{deck['id']}").json()
    assert restored["generation_metadata"]["generation_version"] == "deck-content-v2"
    assert restored["slides"][1]["assets"][0]["status"] == "ready"
    assert state["image_calls"] == before


def test_partial_image_retry_reuses_prompt_successful_assets_and_other_pages(decks, settings):
    client, state, _ = decks
    composition = image_pipeline(client, state)
    state["extra_asset"], state["fail_image_call"] = True, 2
    notebook, _ = notebook_with_source(client)
    deck, job = create_deck(client, notebook)
    assert job["status"] == "completed" and deck["status"] == "partial"
    slide = deck["slides"][1]
    assert [a["status"] for a in slide["assets"]] == ["ready", "failed"]
    assert len(composition.calls) == 9
    assert state["image_calls"] == 2
    with client.app.state.db.connect() as conn:
        ready = dict(conn.execute("SELECT * FROM assets WHERE status='ready'").fetchone())
        prompt = conn.execute("SELECT prompt FROM assets WHERE status='failed'").fetchone()[0]
    assert "纸张纹理" in prompt
    before = len(state["calls"])
    retry = client.post(f"/api/decks/{deck['id']}/slides/{slide['id']}/retry")
    assert retry.status_code == 202
    assert wait_for_job(client, retry.json()["id"])["status"] == "completed"
    result = client.get(f"/api/decks/{deck['id']}").json()
    assert result["status"] == "draft"
    assert state["image_calls"] == 3 and len(state["calls"]) == before + 1
    assert composition.calls[-1] == (slide["id"], {"metaphor", "second"})
    assert len(composition.calls) == 10
    with client.app.state.db.connect() as conn:
        assert (
            dict(conn.execute("SELECT * FROM assets WHERE id=?", (ready["id"],)).fetchone())
            == ready
        )
    assert (settings.data_dir / ready["file_uri"]).is_file()
    for index, other in enumerate(result["slides"]):
        if index != 1:
            assert other == deck["slides"][index]


def test_continue_without_failed_image_preserves_ready_asset_and_survives_restart(decks, settings):

    client, state, transport = decks
    composition = image_pipeline(client, state)
    state["extra_asset"], state["fail_image_call"] = True, 2
    notebook, _ = notebook_with_source(client)
    deck, _ = create_deck(client, notebook)
    slide = deck["slides"][1]
    before = len(state["calls"])
    response = client.post(f"/api/decks/{deck['id']}/slides/{slide['id']}/without-image")
    assert wait_for_job(client, response.json()["id"])["status"] == "completed"
    result = client.get(f"/api/decks/{deck['id']}").json()
    assert result["status"] == "draft" and len(state["calls"]) == before
    assert composition.calls[-1] == (slide["id"], {"metaphor"})
    assert [a["status"] for a in result["slides"][1]["assets"]] == ["ready", "skipped"]
    other, _ = create_deck(client, notebook)
    assert client.post(f"/api/decks/{other['id']}/slides/{slide['id']}/retry").status_code == 404
    with restart(client, settings, transport=transport) as restarted:
        saved = restarted.get(f"/api/decks/{deck['id']}").json()
        assert saved["slides"][1]["assets"] == result["slides"][1]["assets"]
