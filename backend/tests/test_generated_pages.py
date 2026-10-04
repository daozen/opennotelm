import asyncio
from io import BytesIO

import pytest
from opennotelm.composition import CompositionService
from opennotelm.schemas import ImageGenerationSettingsInput
from PIL import Image
from pypdf import PdfReader
from restart_support import restart
from test_decks import create_deck, notebook_with_source
from test_decks import decks as deck_fixture
from test_models import config
from test_revisions import submit, unchanged_siblings
from test_sources import wait_for_job


class NoNativeRenderer:
    async def preflight(self, *args):
        raise AssertionError("Whole-page generation must not plan native geometry")

    async def render(self, *args):
        raise AssertionError("Whole-page images must not receive native text overlays")


@pytest.fixture
def pages(settings):
    for client, state, transport in deck_fixture.__wrapped__(settings):
        assert client.post("/api/settings/models/test", json=config("image")).status_code == 200
        service = CompositionService(
            client.app.state.db, client.app.state.models, settings, NoNativeRenderer()
        )
        client.app.state.decks.composition = service
        client.app.state.decks.assets = client.app.state.assets
        client.app.state.decks.exports = client.app.state.pdf_exports
        yield client, state, transport


def new_page_deck(client, notebook, count=10):
    # Omit render_mode to exercise the application's new default.
    response = client.post(f"/api/notebooks/{notebook}/decks", json={"slide_count": count})
    assert response.status_code == 202, response.text
    created = response.json()
    job = wait_for_job(client, created["job"]["id"])
    return client.get(f"/api/decks/{created['id']}").json(), job


@pytest.mark.parametrize("concurrency", [1, 2, 20])
def test_page_workers_obey_limit_and_export_in_source_order(pages, concurrency):
    client, _, _ = pages
    service = client.app.state.decks
    assert (
        client.put(
            "/api/settings/models/image-generation", json={"concurrency": concurrency}
        ).status_code
        == 200
    )
    count = 20 if concurrency == 20 else 10
    adapter = client.app.state.models.gateway.images
    original = adapter.generate
    active = peak = started = 0
    finished = []
    progresses = []
    stage = service.stage

    def track_stage(deck_id, context, name, progress):
        if progress >= 0.75:
            progresses.append(progress)
        stage(deck_id, context, name, progress)

    async def slow_image(*args, **kwargs):
        nonlocal active, peak, started
        started += 1
        index = started
        active += 1
        peak = max(peak, active)
        try:
            await asyncio.sleep(0.08 if index % 2 else 0.01)
            result = await original(*args, **kwargs)
            finished.append(index)
            return result
        finally:
            active -= 1

    adapter.generate = slow_image
    service.stage = track_stage
    notebook, _ = notebook_with_source(client)
    deck, job = new_page_deck(client, notebook, count)
    assert deck["status"] == "ready" and job["status"] == "completed"
    assert peak == concurrency and active == 0 and started == count
    assert deck["generation_metadata"]["image_generation_concurrency"] == concurrency
    assert progresses == sorted(progresses)
    assert finished[0] == (2 if concurrency > 1 else 1)
    reader = PdfReader(BytesIO(client.get(deck["pdf_export"]["download_url"]).content))
    assert [entry.title for entry in reader.outline] == [
        s["spec"]["content_elements"][0]["text"] for s in deck["slides"]
    ]


def test_running_job_keeps_limit_when_settings_change_during_authoring(pages):
    client, _, _ = pages
    service = client.app.state.decks
    author = service.author
    adapter = client.app.state.models.gateway.images
    original = adapter.generate
    active = peak = 0

    async def change_settings(*args):
        service.image_generation_settings.save(ImageGenerationSettingsInput(concurrency=20))
        await author(*args)

    async def slow_image(*args, **kwargs):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        try:
            await asyncio.sleep(0.02)
            return await original(*args, **kwargs)
        finally:
            active -= 1

    service.author = change_settings
    adapter.generate = slow_image
    notebook, _ = notebook_with_source(client)
    deck, job = new_page_deck(client, notebook)
    assert job["status"] == "completed" and deck["status"] == "ready"
    assert peak == 2 and active == 0
    assert deck["generation_metadata"]["image_generation_concurrency"] == 2
    assert client.get("/api/settings/models/image-generation").json()["concurrency"] == 20


def test_interrupt_cancels_all_inflight_pages_and_resumes(pages):
    client, _, _ = pages
    adapter = client.app.state.models.gateway.images
    original = adapter.generate
    active = cancelled = 0

    async def blocked(*args, **kwargs):
        nonlocal active, cancelled
        active += 1
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled += 1
            raise
        finally:
            active -= 1

    adapter.generate = blocked
    notebook, _ = notebook_with_source(client)
    created = client.post(f"/api/notebooks/{notebook}/decks", json={"slide_count": 10}).json()

    async def interrupt():
        async with asyncio.timeout(20):
            while active < 2:
                await asyncio.sleep(0.01)
        await client.app.state.jobs.stop()

    client.portal.call(interrupt)
    assert active == 0 and cancelled == 2
    assert client.get(f"/api/jobs/{created['job']['id']}").json()["status"] == "queued"
    adapter.generate = original
    client.portal.call(client.app.state.jobs.start)
    assert wait_for_job(client, created["job"]["id"])["status"] == "completed"
    updated = client.get(f"/api/decks/{created['id']}").json()
    assert updated["status"] == "ready" and len(updated["slides"]) == 10


def test_content_copy_reauthors_every_page_without_changing_original(pages):
    client, state, _ = pages
    notebook, _ = notebook_with_source(client)
    original, _ = new_page_deck(client, notebook)
    # Simulate saved legacy copy; it must remain untouched while the new copy is authored.
    import json

    with client.app.state.db.connect() as conn:
        spec = original["slides"][0]["spec"]
        spec["content_elements"][1]["label"] = "作者见解"
        conn.execute(
            "UPDATE slides SET spec_json=? WHERE id=?",
            (json.dumps(spec), original["slides"][0]["id"]),
        )
    baseline = client.get(f"/api/decks/{original['id']}").json()
    before = len(state["calls"])
    created = client.post(f"/api/decks/{original['id']}/generated-copy?rewrite_content=true").json()
    assert wait_for_job(client, created["job"]["id"])["status"] == "completed"
    rewritten = client.get(f"/api/decks/{created['id']}").json()
    assert rewritten["status"] == "ready"
    assert rewritten["generation_metadata"]["rewritten_content"]
    assert rewritten["generation_metadata"]["content_policy_version"] == "source-interpretation-v2"
    assert rewritten["generation_metadata"]["replanned_content"]
    assert "作者见解" not in str(rewritten["slides"])
    assert rewritten["source_scope"] == baseline["source_scope"]
    assert rewritten["generation_metadata"]["restyled"]
    assert rewritten["generation_metadata"]["visual_style_version"] == "content-adaptive-style-v1"
    assert len(rewritten["slides"]) == len(baseline["slides"])
    assert (
        rewritten["plan"]["slides"][0]["evidence_ids"]
        != baseline["plan"]["slides"][0]["evidence_ids"]
    )
    calls = state["calls"][before:]
    assert (
        sum(
            c.get("messages", [{}])[0].get("content", "").startswith("Author one SlideSpec")
            for c in calls
        )
        == 10
    )
    assert client.get(f"/api/decks/{original['id']}").json() == baseline


def test_rewriting_shortened_deck_keeps_its_pages_and_valid_evidence(pages):
    client, _, _ = pages
    notebook, _ = notebook_with_source(client)
    original, _ = new_page_deck(client, notebook)
    removed = original["slides"][-1]
    response = client.request(
        "DELETE",
        f"/api/decks/{original['id']}/slides/{removed['id']}",
        json={"revision": removed["revision"]},
    )
    assert response.status_code == 200
    baseline = client.get(f"/api/decks/{original['id']}").json()
    assert wait_for_job(client, baseline["job"]["id"])["status"] == "completed"
    baseline = client.get(f"/api/decks/{original['id']}").json()
    copied = client.post(f"/api/decks/{original['id']}/generated-copy?rewrite_content=true").json()
    assert wait_for_job(client, copied["job"]["id"])["status"] == "completed"
    updated = client.get(f"/api/decks/{copied['id']}").json()
    assert updated["status"] == "ready" and len(updated["slides"]) == 9
    assert not updated["generation_metadata"]["replanned_content"]
    assert [s["plan"] for s in updated["slides"]] == [s["plan"] for s in baseline["slides"]]
    assert all(s["spec"] and s["citations"] for s in updated["slides"])
    assert client.get(f"/api/decks/{original['id']}").json() == baseline


def test_default_generates_every_complete_page_without_layout_calls_and_exports(pages, settings):
    client, state, transport = pages
    notebook, _ = notebook_with_source(client)
    deck, job = new_page_deck(client, notebook)
    assert job["status"] == "completed" and deck["status"] == "ready"
    assert deck["render_mode"] == "generated_page"
    assert deck["generation_metadata"]["generation_version"] == "deck-content-v5"
    assert deck["art_direction"]["metrics"]["longest_form_run"] == 1
    calls = [c for c in state["calls"] if "messages" in c]
    assert not any(
        c["messages"][0]["content"].startswith(
            ("Design an original visual composition", "Write one image-generation prompt")
        )
        for c in calls
    )
    images = [c for c in state["calls"] if "prompt" in c and c.get("size")]
    assert len(images) == 10 and all(c["size"] == "2048x1152" for c in images)
    for slide, payload in zip(deck["slides"], images, strict=True):
        assert len(slide["assets"]) == 1 and slide["assets"][0]["request_id"] == "full_page"
        assert slide["render"]["text_layer"] == [] and slide["render"]["mode"] == "generated_page"
        assert slide["render"]["width"] == 2048 and slide["render"]["height"] == 1152
        assert all(marker not in payload["prompt"] for marker in slide["citations"])
        heading = slide["spec"]["content_elements"][0]["text"]
        assert heading in payload["prompt"] and '"exact_visible_copy"' in payload["prompt"]
        for identity in slide["citations"].values():
            assert client.get(f"/api/citations/{identity}").json()["available"]
        with client.app.state.db.connect() as conn:
            asset = conn.execute(
                "SELECT file_uri FROM assets WHERE id=?", (slide["assets"][0]["id"],)
            ).fetchone()
        assert (
            client.get(slide["render"]["image_url"]).content
            == (settings.data_dir / asset[0]).read_bytes()
        )
    with client.app.state.db.connect() as conn:
        assert conn.execute("SELECT count(*) FROM slide_designs").fetchone()[0] == 0
    exported = client.get(deck["pdf_export"]["download_url"])
    preview = client.get(deck["pdf_export"]["preview_url"])
    assert preview.content == exported.content and preview.headers[
        "content-disposition"
    ].startswith("inline;")
    reader = PdfReader(BytesIO(exported.content))
    assert len(reader.pages) == len(reader.outline) == 10
    assert all(not page.extract_text().strip() for page in reader.pages)
    source = Image.open(
        BytesIO(client.get(deck["slides"][0]["render"]["image_url"]).content)
    ).convert("RGB")
    recovered = reader.pages[0].images[0].image.convert("RGB")
    assert recovered.size == source.size and recovered.tobytes() == source.tobytes()
    with restart(client, settings, transport=transport) as restarted:
        restored = restarted.get(f"/api/decks/{deck['id']}").json()
        assert restored["slides"] == deck["slides"]
        assert restarted.get(restored["pdf_export"]["download_url"]).content == exported.content


def test_failed_page_retry_keeps_siblings_and_cannot_skip_the_complete_image(pages):
    client, state, _ = pages
    notebook, _ = notebook_with_source(client)
    state["fail_image_call"] = state["image_calls"] + 3
    deck, job = new_page_deck(client, notebook)
    assert job["status"] == "completed" and deck["status"] == "partial"
    failed = deck["slides"][2]
    assert failed["status"] == "failed" and not deck["pdf_export"]
    skip = client.post(f"/api/decks/{deck['id']}/slides/{failed['id']}/without-image")
    assert skip.status_code == 409 and skip.json()["error"]["code"] == "PAGE_IMAGE_REQUIRED"
    before = len(state["calls"])
    response = client.post(f"/api/decks/{deck['id']}/slides/{failed['id']}/retry")
    assert wait_for_job(client, response.json()["id"])["status"] == "completed"
    updated = client.get(f"/api/decks/{deck['id']}").json()
    unchanged_siblings(deck, updated, failed["id"])
    assert updated["status"] == "ready" and len(state["calls"]) == before + 1


@pytest.mark.parametrize("action", ["text", "visual", "image", "content"])
def test_each_revision_regenerates_only_that_full_page_and_keeps_sources(pages, action):
    client, state, _ = pages
    notebook, _ = notebook_with_source(client)
    deck, _ = new_page_deck(client, notebook)
    slide = deck["slides"][0]
    images = state["image_calls"]
    before = len(state["calls"])
    if action == "text":
        response = client.patch(
            f"/api/decks/{deck['id']}/slides/{slide['id']}/text",
            json={
                "revision": slide["revision"],
                "changes": [{"ref": "heading", "text": "整页中的新标题"}],
            },
        )
        assert response.status_code == 202
        job = wait_for_job(client, response.json()["id"])
        updated = client.get(f"/api/decks/{deck['id']}").json()
        assert "整页中的新标题" in state["calls"][-1]["prompt"]
    else:
        updated, job = submit(client, deck, slide, action, "更直观地呈现本页关系")
    assert job["status"] == "completed" and updated["status"] == "ready"
    assert state["image_calls"] == images + 1
    assert len(state["calls"]) == before + (3 if action == "content" else 1)
    changed = updated["slides"][0]
    assert changed["render_current"] and changed["revision"] == slide["revision"] + 1
    assert changed["assets"][0]["id"] != slide["assets"][0]["id"]
    assert changed["render"]["id"] != slide["render"]["id"]
    if action == "content":
        assert changed["citations"].keys() == slide["citations"].keys()
        for citation in changed["citations"].values():
            assert client.get(f"/api/citations/{citation}").json()["available"]
    else:
        assert changed["citations"] == slide["citations"]
    unchanged_siblings(deck, updated, slide["id"])
    assert updated["pdf_export"]["id"] != deck["pdf_export"]["id"]
    assert client.get(deck["pdf_export"]["download_url"]).status_code == 409


def test_missing_render_reuses_saved_page_image_without_another_model_call(pages, settings):
    client, state, _ = pages
    notebook, _ = notebook_with_source(client)
    deck, _ = new_page_deck(client, notebook)
    slide = deck["slides"][0]
    with client.app.state.db.connect() as conn:
        row = conn.execute(
            "SELECT native_pdf_uri FROM slide_renders WHERE id=?", (slide["render"]["id"],)
        ).fetchone()
        (settings.data_dir / row[0]).unlink()
        conn.execute("UPDATE slides SET status='failed' WHERE id=?", (slide["id"],))
    before = len(state["calls"])
    response = client.post(f"/api/decks/{deck['id']}/slides/{slide['id']}/retry")
    assert wait_for_job(client, response.json()["id"])["status"] == "completed"
    updated = client.get(f"/api/decks/{deck['id']}").json()
    assert len(state["calls"]) == before and updated["status"] == "ready"
    assert updated["slides"][0]["render"]["id"] != slide["render"]["id"]
    unchanged_siblings(deck, updated, slide["id"])


@pytest.mark.parametrize("source_mode", ["native", "generated_page", "shortened_generated_page"])
def test_generated_copy_preserves_old_deck_and_reuses_exact_grounded_content(pages, source_mode):
    client, state, _ = pages
    notebook, _ = notebook_with_source(client)
    composition, exports = client.app.state.decks.composition, client.app.state.decks.exports
    if source_mode == "native":
        client.app.state.decks.composition, client.app.state.decks.exports = None, None
        original, _ = create_deck(client, notebook)
    else:
        original, _ = new_page_deck(client, notebook)
    client.app.state.decks.composition, client.app.state.decks.exports = composition, exports
    if source_mode == "shortened_generated_page":
        slide = original["slides"][-1]
        response = client.request(
            "DELETE",
            f"/api/decks/{original['id']}/slides/{slide['id']}",
            json={"revision": slide["revision"]},
        )
        assert response.status_code == 200, response.text
        original = client.get(f"/api/decks/{original['id']}").json()
        assert wait_for_job(client, original["job"]["id"])["status"] == "completed"
        original = client.get(f"/api/decks/{original['id']}").json()
    before = len(state["calls"])
    response = client.post(f"/api/decks/{original['id']}/generated-copy")
    assert response.status_code == 202, response.text
    created = response.json()
    assert wait_for_job(client, created["job"]["id"])["status"] == "completed"
    copy = client.get(f"/api/decks/{created['id']}").json()
    assert copy["status"] == "ready" and copy["render_mode"] == "generated_page"
    assert len(state["calls"]) == before + 1 + len(original["slides"])
    assert copy["generation_metadata"]["copied_from_deck_id"] == original["id"]
    assert set(copy["art_direction"]["pages"]) == {s["id"] for s in copy["slides"]}
    assert set(copy["art_direction"]["pages"]).isdisjoint(s["id"] for s in original["slides"])
    assert copy["style"] == original["style"]
    assert copy["plan"] == {
        **original["plan"],
        "slides": [slide["plan"] for slide in original["slides"]],
    }
    assert [s["spec"] for s in copy["slides"]] == [s["spec"] for s in original["slides"]]
    assert client.get(f"/api/decks/{original['id']}").json() == original
    assert {s["id"] for s in copy["slides"]}.isdisjoint(s["id"] for s in original["slides"])
    for old, new in zip(original["slides"], copy["slides"], strict=True):
        assert new["citations"].keys() == old["citations"].keys()
        for marker, citation in new["citations"].items():
            source = client.get(f"/api/citations/{old['citations'][marker]}").json()
            target = client.get(f"/api/citations/{citation}").json()
            assert [s["quote"] for s in source["spans"]] == [s["quote"] for s in target["spans"]]


def test_generated_pages_require_image_configuration_before_enqueuing(settings):
    for client, _state, _ in deck_fixture.__wrapped__(settings):
        notebook, _ = notebook_with_source(client)
        response = client.post(f"/api/notebooks/{notebook}/decks", json={"slide_count": 10})
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "MODEL_NOT_CONFIGURED"
        assert client.get(f"/api/notebooks/{notebook}/decks").json() == []


def test_wrong_aspect_ratio_is_failed_instead_of_cropping_words(pages):
    from image_factory import image_bytes
    from opennotelm.image_adapter import validated_image

    client, _state, _ = pages
    notebook, _ = notebook_with_source(client)

    async def square(*args, **kwargs):
        return validated_image(image_bytes())

    client.app.state.models.gateway.images.generate = square
    deck, _ = new_page_deck(client, notebook)
    assert deck["status"] == "partial" and deck["pdf_export"] is None
    assert all(s["error_code"] == "PAGE_IMAGE_SIZE_INVALID" for s in deck["slides"])
    assert all(not s["render"] for s in deck["slides"])


def test_stop_and_resume_reuses_completed_images_and_joins_all_page_workers(pages):
    client, state, _ = pages
    notebook, _ = notebook_with_source(client)
    adapter = client.app.state.models.gateway.images
    original = adapter.generate
    active = entered = 0

    async def blocked_after_first(*args, **kwargs):
        nonlocal active, entered
        entered += 1
        if entered == 1:
            return await original(*args, **kwargs)
        active += 1
        try:
            await asyncio.Event().wait()
        finally:
            active -= 1

    adapter.generate = blocked_after_first
    created = client.post(f"/api/notebooks/{notebook}/decks", json={"slide_count": 10}).json()
    identity, job_id = created["id"], created["job"]["id"]

    async def wait_saved():
        async with asyncio.timeout(5):
            while active != 2 or not any(
                s["render"] for s in client.app.state.decks.get(identity)["slides"]
            ):
                await asyncio.sleep(0.01)

    client.portal.call(wait_saved)
    before = client.get(f"/api/decks/{identity}").json()
    saved = next(s for s in before["slides"] if s["render"])
    before_images = state["image_calls"]
    stopped = client.post(f"/api/decks/{identity}/stop").json()
    assert active == 0 and stopped["job"]["status"] == "cancelled"
    assert stopped["slides"] == before["slides"]
    adapter.generate = original
    assert client.post(f"/api/decks/{identity}/resume").status_code == 202
    assert wait_for_job(client, job_id)["status"] == "completed"
    finished = client.get(f"/api/decks/{identity}").json()
    assert finished["status"] == "ready" and finished["pdf_export"]["page_count"] == 10
    assert (
        next(s for s in finished["slides"] if s["id"] == saved["id"])["render"] == saved["render"]
    )
    assert state["image_calls"] == before_images + 9


def test_delete_during_pdf_assembly_joins_thread_before_removing_owned_files(pages, monkeypatch):
    import threading

    import opennotelm.pdf_export as exports

    client, _, _ = pages
    notebook, source = notebook_with_source(client)
    entered, release, returned = threading.Event(), threading.Event(), threading.Event()
    original = exports.assemble_pdf

    def blocked(*args):
        entered.set()
        assert release.wait(5)
        return original(*args)

    monkeypatch.setattr(exports, "assemble_pdf", blocked)
    created = client.post(f"/api/notebooks/{notebook}/decks", json={"slide_count": 10}).json()
    identity = created["id"]
    assert entered.wait(5)
    responses = []

    def delete():
        responses.append(client.delete(f"/api/decks/{identity}"))
        returned.set()

    deleting = threading.Thread(target=delete)
    deleting.start()
    try:
        assert not returned.wait(0.05)
    finally:
        release.set()
        deleting.join(timeout=5)
    assert returned.is_set() and responses[0].status_code == 204
    assert client.get(f"/api/decks/{identity}").status_code == 404
    with client.app.state.db.connect() as conn:
        assert not conn.execute("SELECT 1 FROM garbage_files").fetchone()
    root = client.app.state.sources.settings.data_dir
    assert all(
        not list((root / directory).iterdir()) for directory in ["assets", "renders", "exports"]
    )
    assert client.get(f"/api/sources/{source}").status_code == 200


def test_stopped_page_revision_resumes_its_payload_without_applying_text_twice(pages):
    client, _, _ = pages
    notebook, _ = notebook_with_source(client)
    deck, _ = new_page_deck(client, notebook)
    slide = deck["slides"][0]
    adapter = client.app.state.models.gateway.images
    original = adapter.generate

    async def blocked(*args, **kwargs):
        await asyncio.Event().wait()

    adapter.generate = blocked
    response = client.patch(
        f"/api/decks/{deck['id']}/slides/{slide['id']}/text",
        json={
            "revision": slide["revision"],
            "changes": [{"ref": "heading", "text": "Saved updated heading"}],
        },
    )
    assert response.status_code == 202
    identity = response.json()["id"]

    async def wait_applied():
        async with asyncio.timeout(5):
            while client.app.state.jobs.get(identity)["stage"] != "generating_assets":
                await asyncio.sleep(0.01)

    client.portal.call(wait_applied)
    paused = client.post(f"/api/decks/{deck['id']}/stop").json()
    assert paused["job"]["id"] == identity and paused["job"]["type"] == "slide_revision"
    applied = paused["slides"][0]
    assert applied["revision"] == slide["revision"] + 1
    assert applied["spec"]["content_elements"][0]["text"] == "Saved updated heading"
    adapter.generate = original
    resumed = client.post(f"/api/decks/{deck['id']}/resume").json()
    assert (
        resumed["job"]["id"] == identity and resumed["job"]["payload"] == paused["job"]["payload"]
    )
    assert wait_for_job(client, identity)["status"] == "completed"
    finished = client.get(f"/api/decks/{deck['id']}").json()
    assert finished["status"] == "ready"
    assert finished["slides"][0]["revision"] == applied["revision"]
    assert finished["slides"][0]["spec"] == applied["spec"]
    assert finished["slides"][1:] == paused["slides"][1:]


def test_author_failure_preserves_content_and_retries_only_missing_page(pages):
    client, state, _ = pages
    notebook, _ = notebook_with_source(client)
    state["fail_slide"] = 10
    deck, job = new_page_deck(client, notebook)
    assert job["status"] == "completed" and deck["status"] == "partial"
    assert len([s for s in deck["slides"] if s["spec"]]) == 9
    failed = deck["slides"][9]
    assert failed["status"] == "failed" and failed["error_code"] != "DECK_CONTENT_REQUIRED"
    assert not deck["pdf_export"]
    assert deck["generation_metadata"]["content_generation_concurrency"] == 2
    before = len(state["calls"])
    state["fail_slide"] = None
    response = client.post(f"/api/decks/{deck['id']}/retry")
    assert response.status_code == 202, response.text
    assert wait_for_job(client, response.json()["id"])["status"] == "completed"
    updated = client.get(f"/api/decks/{deck['id']}").json()
    authors = [
        c
        for c in state["calls"][before:]
        if c.get("messages", [{}])[0].get("content", "").startswith("Author one SlideSpec")
    ]
    assert len(authors) == 1 and updated["status"] == "ready"
    assert [s["spec"] for s in updated["slides"][:9]] == [s["spec"] for s in deck["slides"][:9]]
    assert (
        len(PdfReader(BytesIO(client.get(updated["pdf_export"]["download_url"]).content)).pages)
        == 10
    )
