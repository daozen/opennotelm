import json

import httpx
import pytest
from deck_provider import deck_completion
from fastapi.testclient import TestClient
from grounded_provider import completion
from image_factory import image_response
from opennotelm.main import create_app
from restart_support import restart
from test_knowledge import create_page, import_text
from test_models import config
from test_sources import wait_for_job


@pytest.fixture
def decks(settings):
    state = {"calls": [], "fail_slide": None, "bad_plan": False, "bad_citations": False}

    def handler(request):
        payload = json.loads(request.content)
        state["calls"].append(payload)
        if request.url.path.endswith("/images/generations"):
            state["image_calls"] = state.get("image_calls", 0) + 1
            if state.get("fail_image") or state["image_calls"] == state.get("fail_image_call"):
                return httpx.Response(503)
            return httpx.Response(200, json=image_response(payload.get("size")))
        system = payload["messages"][0]["content"]
        value = None
        if system.startswith(
            (
                "Resolve deck content preferences.",
                "Create a DeckBrief.",
                "Plan the narrative",
                "Define a unique DeckStyleManifest.",
                "Author one SlideSpec",
                "Design an original visual composition",
                "Write one image-generation prompt",
                "Choose which layer of one slide",
                "Art-direct the complete illustrated deck",
            )
        ):
            data = json.loads(payload["messages"][-1]["content"])
            if (
                system.startswith("Author one SlideSpec")
                and data["slide_plan"]["index"] == state["fail_slide"]
            ):
                return httpx.Response(503)
            value = deck_completion(payload)
            if system.startswith("Define a unique DeckStyleManifest.") and state.get(
                "style_palette_override"
            ):
                value.get("style", value)["palette"] = state["style_palette_override"]
            if system.startswith("Art-direct the complete illustrated deck") and state.get(
                "bad_art"
            ):
                for page in value["pages"]:
                    page["form"] = "object_annotation"
            if system.startswith("Plan the narrative") and state["bad_plan"]:
                value["slides"] = value["slides"][:-1]
            if system.startswith("Author one SlideSpec") and state["bad_citations"]:
                value["content_elements"][1]["citations"] = ["FAKE"]
            if system.startswith("Author one SlideSpec") and state.get("added_editorial_note"):
                value["content_elements"][1]["type"] = "statement"
                value["content_elements"][1]["label"] = "解读边界"
                value["content_elements"][1]["text"] = "这不是此处独立验证的普遍定论。"
                state["added_editorial_note"] = False
            if (
                system.startswith("Author one SlideSpec")
                and value["asset_requests"]
                and state.get("extra_asset")
            ):
                value["asset_requests"].append({**value["asset_requests"][0], "id": "second"})
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(value, ensure_ascii=False)
                            if value
                            else completion(payload)
                        }
                    }
                ]
            },
        )

    transport = httpx.MockTransport(handler)
    with TestClient(create_app(settings, transport=transport)) as client:
        # Content-pipeline unit tests isolate browser rendering, covered by renderer/E2E tests.
        client.app.state.decks.composition = None
        client.app.state.decks.assets = None
        client.app.state.decks.exports = None
        assert client.post("/api/settings/models/test", json=config("language")).status_code == 200
        yield client, state, transport


def notebook_with_source(client):
    notebook = client.post("/api/notebooks", json={"title": "Deck"}).json()["id"]
    source = import_text(
        client,
        notebook,
        "# Time\n\nSmall improvements accumulate over time.\n\n"
        "## Practice\n\nDaily reflection helps learning.",
    )
    return notebook, source


def create_deck(client, notebook, count=10, scope=None, render_mode="native"):
    response = client.post(
        f"/api/notebooks/{notebook}/decks",
        json={
            "slide_count": count,
            "scope": scope or {"kind": "selected"},
            "language": "zh-CN",
            "instruction": "帮助初学者理解",
            "render_mode": render_mode,
        },
    )
    assert response.status_code == 202, response.text
    value = response.json()
    job = wait_for_job(client, value["job"]["id"])
    return client.get(f"/api/decks/{value['id']}").json(), job


@pytest.mark.parametrize("count", [10, 15, 20])
def test_exact_length_rich_semantics_dynamic_style_and_original_citations(decks, count):
    client, state, _ = decks
    notebook, source = notebook_with_source(client)
    other = import_text(client, notebook, "UNSELECTED_SENTINEL")
    client.patch(f"/api/notebooks/{notebook}/sources/{other}", json={"enabled": False})
    deck, job = create_deck(client, notebook, count)
    assert job["status"] == "completed", job
    assert deck["status"] == "draft"
    assert len(deck["slides"]) == count
    assert deck["style"]["concept"] == "时间沉积的层次"
    assert deck["brief"]["language"] == "zh-CN"
    assert [s["ordinal"] for s in deck["slides"]] == list(range(count))
    kinds = {e["type"] for s in deck["slides"] for e in s["spec"]["content_elements"]}
    assert {"comparison", "quote", "statement", "bullet_list"} <= kinds
    assert any(s["spec"]["asset_requests"] for s in deck["slides"])
    assert all(s["status"] == "authored" for s in deck["slides"])
    for slide in deck["slides"]:
        assert slide["citations"]
        for ref in slide["citations"].values():
            citation = client.get(f"/api/citations/{ref}").json()
            assert citation["owner_id"] == slide["id"]
            assert citation["spans"][0]["source_id"] == source
            assert citation["spans"][0]["quote"]
    prompts = json.dumps(state["calls"], ensure_ascii=False)
    assert "UNSELECTED_SENTINEL" not in prompts
    assert client.get("/api/notebooks").json()[0]["deck_count"] == 1
    assert "understanding" not in deck


def test_partial_retry_preserves_completed_slides_and_plan(decks, settings):
    client, state, transport = decks
    notebook, _ = notebook_with_source(client)
    state["fail_slide"] = 3
    deck, job = create_deck(client, notebook)
    assert job["status"] == "completed" and deck["status"] == "partial"
    assert [s["ordinal"] for s in deck["slides"] if s["status"] == "failed"] == [2]
    complete = {s["id"]: s for s in deck["slides"] if s["status"] == "authored"}
    original_plan, original_style = deck["plan"], deck["style"]
    before = len(state["calls"])
    state["fail_slide"] = None
    retry = client.post(f"/api/decks/{deck['id']}/retry").json()
    assert wait_for_job(client, retry["id"])["status"] == "completed"
    updated = client.get(f"/api/decks/{deck['id']}").json()
    assert updated["status"] == "draft"
    assert len(state["calls"]) == before + 1
    assert updated["plan"] == original_plan and updated["style"] == original_style
    for slide in updated["slides"]:
        if slide["id"] in complete:
            assert slide == complete[slide["id"]]
    with restart(client, settings, transport=transport) as restarted:
        assert restarted.get(f"/api/decks/{deck['id']}").json()["slides"] == updated["slides"]


def test_bad_count_or_evidence_is_not_published(decks):
    client, state, _ = decks
    notebook, _ = notebook_with_source(client)
    assert (
        client.post(f"/api/notebooks/{notebook}/decks", json={"slide_count": 12}).status_code == 422
    )
    state["bad_plan"] = True
    deck, job = create_deck(client, notebook)
    assert job["status"] == "failed" and deck["status"] == "failed"
    assert not deck["slides"] and deck["plan"] is None
    assert (
        len(
            [
                c
                for c in state["calls"]
                if c["messages"][0]["content"].startswith("Plan the narrative")
            ]
        )
        == 2
    )
    state["bad_plan"] = False
    state["bad_citations"] = True
    retry = client.post(f"/api/decks/{deck['id']}/retry").json()
    assert wait_for_job(client, retry["id"])["status"] == "completed"
    updated = client.get(f"/api/decks/{deck['id']}").json()
    assert updated["status"] == "partial"
    assert all(s["spec"] is None and not s["citations"] for s in updated["slides"])


def test_knowledge_snapshot_and_chapter_scope(decks):
    client, state, _ = decks
    notebook, source = notebook_with_source(client)
    nodes = client.get(f"/api/sources/{source}/nodes").json()
    scope = {"kind": "node", "source_id": source, "node_id": nodes[-1]["id"]}
    page, job = create_page(client, notebook, scope)
    assert job["status"] == "completed"
    client.portal.call(client.app.state.jobs.stop)
    response = client.post(
        f"/api/notebooks/{notebook}/decks",
        json={
            "slide_count": 10,
            "render_mode": "native",
            "scope": {"kind": "knowledge", "knowledge_page_id": page["id"]},
        },
    ).json()
    client.patch(
        f"/api/knowledge/{page['id']}",
        json={
            "revision": page["revision"],
            "title": "Edited",
            "content_markdown": "An unrelated new edit.",
        },
    )
    client.portal.call(client.app.state.jobs.run_one)
    deck = client.get(f"/api/decks/{response['id']}").json()
    assert deck["status"] == "draft"
    assert deck["generation_metadata"]["knowledge_revision"] == page["revision"]
    assert "An unrelated new edit" not in json.dumps(state["calls"])
    assert all(s["spec"] for s in deck["slides"])
    other = client.post("/api/notebooks", json={"title": "Other"}).json()["id"]
    assert (
        client.post(
            f"/api/notebooks/{other}/decks",
            json={
                "render_mode": "native",
                "scope": {"kind": "knowledge", "knowledge_page_id": page["id"]},
            },
        ).status_code
        == 400
    )


def test_deleted_sources_keep_existing_deck_and_mark_citations_unavailable(decks):
    client, _, _ = decks
    notebook, source = notebook_with_source(client)
    deck, job = create_deck(client, notebook)
    assert job["status"] == "completed"
    assert client.delete(f"/api/sources/{source}").status_code == 204
    saved = client.get(f"/api/decks/{deck['id']}").json()
    assert saved["slides"] == deck["slides"]
    for ref in saved["slides"][0]["citations"].values():
        assert not client.get(f"/api/citations/{ref}").json()["available"]


def test_render_pipeline_caches_pages_and_retries_only_failed_render(decks, settings):
    from opennotelm.composition import CompositionService
    from opennotelm.errors import AppError

    client, state, _ = decks

    class FakeRenderer:
        fail = True
        calls = []

        async def render(self, render, fragments, style, assets, directory):
            self.calls.append(fragments[0]["text"])
            if self.fail and "第 3 步" in fragments[0]["text"]:
                raise AppError("RENDER_BROWSER_FAILED", "Simulated renderer failure")
            directory.mkdir(parents=True, exist_ok=True)
            for filename in ("page.png", "thumbnail.png", "page.pdf"):
                (directory / filename).write_bytes(b"synthetic-render")
            return {
                "text_layer": [
                    {"text": fragment["text"], "bbox": [0, 0, 100, 100]} for fragment in fragments
                ],
                "browser_version": "test",
            }

    renderer = FakeRenderer()
    client.app.state.decks.composition = CompositionService(
        client.app.state.db, client.app.state.models, settings, renderer
    )
    notebook, _ = notebook_with_source(client)
    deck, job = create_deck(client, notebook)
    assert job["status"] == "completed" and deck["status"] == "partial"
    assert sum(bool(slide["render"]) for slide in deck["slides"]) == 9
    saved = {slide["id"]: slide["render"]["id"] for slide in deck["slides"] if slide["render"]}
    before = len(state["calls"])
    renderer.fail = False
    retry = client.post(f"/api/decks/{deck['id']}/retry").json()
    assert wait_for_job(client, retry["id"])["status"] == "completed"
    updated = client.get(f"/api/decks/{deck['id']}").json()
    assert all(slide["render"] for slide in updated["slides"])
    assert len(state["calls"]) == before and len(renderer.calls) == 11
    for slide in updated["slides"]:
        if slide["id"] in saved:
            assert slide["render"]["id"] == saved[slide["id"]]
    image = client.get(updated["slides"][0]["render"]["image_url"])
    assert image.status_code == 200 and image.headers["content-type"] == "image/png"
    assert client.get("/api/renders/missing/image").status_code == 404


def test_layout_repair_feedback_and_no_orphan_output(decks, settings):
    from opennotelm.composition import CompositionService
    from opennotelm.errors import AppError

    client, state, _ = decks
    notebook, _ = notebook_with_source(client)
    deck, _ = create_deck(client, notebook)
    slide = deck["slides"][0]

    class FakeRenderer:
        calls = 0

        async def render(self, render, fragments, style, assets, directory):
            self.calls += 1
            directory.mkdir(parents=True, exist_ok=True)
            error = AppError("RENDER_LAYOUT_INVALID", "Synthetic overflow")
            error.layout_feedback = [{"content_ref": "heading", "reason": "text_overflow"}]
            raise error

    renderer = FakeRenderer()
    service = CompositionService(client.app.state.db, client.app.state.models, settings, renderer)
    record = client.app.state.decks.record(deck["id"])
    with client.app.state.db.connect() as conn:
        row = dict(conn.execute("SELECT * FROM slides WHERE id=?", (slide["id"],)).fetchone())

    async def run():
        await service.render_slide(record, row)

    with pytest.raises(AppError, match="RENDER_LAYOUT_INVALID"):
        client.portal.call(run)
    assert renderer.calls == 2
    last = json.loads(state["calls"][-1]["messages"][-1]["content"])
    assert last["layout_feedback"] == [{"content_ref": "heading", "reason": "text_overflow"}]
    assert list((settings.data_dir / "renders").iterdir()) == []
