import asyncio
import json

import pytest
from opennotelm.composition import CompositionService
from opennotelm.errors import AppError
from test_decks import create_deck, notebook_with_source
from test_decks import decks as deck_fixture
from test_models import config
from test_sources import wait_for_job


class Renderer:
    def __init__(self):
        self.calls, self.fail = [], False

    async def render(self, render, fragments, style, assets, directory):
        self.calls.append((fragments, set(assets)))
        if self.fail:
            raise AppError("RENDER_BROWSER_FAILED", "Synthetic renderer failure")
        directory.mkdir(parents=True, exist_ok=True)
        for name in ("page.png", "thumbnail.png", "page.pdf"):
            (directory / name).write_bytes(b"synthetic-page")
        return {
            "text_layer": [{"text": item["text"], "bbox": [0, 0, 100, 100]} for item in fragments],
            "browser_version": "test",
        }


@pytest.fixture
def revisions(settings):
    for client, state, _transport in deck_fixture.__wrapped__(settings):
        assert client.post("/api/settings/models/test", json=config("image")).status_code == 200
        renderer = Renderer()
        client.app.state.decks.composition = CompositionService(
            client.app.state.db, client.app.state.models, settings, renderer
        )
        client.app.state.decks.assets = client.app.state.assets
        notebook, source = notebook_with_source(client)
        deck, job = create_deck(client, notebook)
        assert job["status"] == "completed" and all(s["render_current"] for s in deck["slides"])
        yield client, state, renderer, deck, source


def submit(client, deck, slide, action, instruction=""):
    response = client.post(
        f"/api/decks/{deck['id']}/slides/{slide['id']}/revise",
        json={
            "revision": slide["revision"],
            "action": action,
            "instruction": instruction,
        },
    )
    assert response.status_code == 202, response.text
    job = wait_for_job(client, response.json()["id"])
    updated = client.get(f"/api/decks/{deck['id']}").json()
    return updated, job


def unchanged_siblings(previous, updated, slide_id):
    for slide in updated["slides"]:
        if slide["id"] != slide_id:
            assert slide == next(s for s in previous["slides"] if s["id"] == slide["id"])
    assert updated["plan"] == previous["plan"] and updated["style"] == previous["style"]


def test_edit_text_only_rerenders_one_page_and_keeps_images_citations(revisions):
    client, state, renderer, deck, _ = revisions
    slide = deck["slides"][1]
    before, images = len(state["calls"]), state["image_calls"]
    response = client.patch(
        f"/api/decks/{deck['id']}/slides/{slide['id']}/text",
        json={
            "revision": slide["revision"],
            "changes": [{"ref": "heading", "text": "我的标题：时间与积累"}],
        },
    )
    assert response.status_code == 202
    assert wait_for_job(client, response.json()["id"])["status"] == "completed"
    updated = client.get(f"/api/decks/{deck['id']}").json()
    changed = updated["slides"][1]
    assert changed["spec"]["content_elements"][0]["text"] == "我的标题：时间与积累"
    assert changed["citations"] == slide["citations"] and changed["assets"] == slide["assets"]
    assert changed["revision"] == slide["revision"] + 1
    assert changed["render_current"] and changed["render"]["id"] != slide["render"]["id"]
    assert len(state["calls"]) == before + 1 and state["image_calls"] == images
    assert len(renderer.calls) == 11
    unchanged_siblings(deck, updated, slide["id"])
    conflict = client.patch(
        f"/api/decks/{deck['id']}/slides/{slide['id']}/text",
        json={
            "revision": slide["revision"],
            "changes": [{"ref": "heading", "text": "Stale"}],
        },
    )
    assert conflict.status_code == 409
    assert (
        client.patch(
            f"/api/decks/{deck['id']}/slides/{slide['id']}/text",
            json={
                "revision": changed["revision"],
                "changes": [{"ref": "missing", "text": "Bad"}],
            },
        ).status_code
        == 400
    )
    with client.app.state.db.connect() as conn:
        record = dict(
            conn.execute(
                "SELECT * FROM slide_revisions WHERE slide_id=?", (slide["id"],)
            ).fetchone()
        )
    assert record["status"] == "completed" and record["stage"] == "completed"
    assert json.loads(json.loads(record["base_snapshot_json"])["spec_json"]) == slide["spec"]


@pytest.mark.parametrize("action,extra_calls", [("visual", 1), ("image", 2), ("content", 2)])
def test_independent_regeneration_preserves_other_pages(revisions, action, extra_calls):
    client, state, renderer, deck, _ = revisions
    slide = deck["slides"][1]
    before, images = len(state["calls"]), state["image_calls"]
    updated, job = submit(client, deck, slide, action)
    assert job["status"] == "completed", job
    changed = updated["slides"][slide["ordinal"]]
    assert len(state["calls"]) == before + extra_calls
    assert len(renderer.calls) == 11 and changed["render"]["id"] != slide["render"]["id"]
    if action != "content":
        assert changed["spec"] == slide["spec"] and changed["citations"] == slide["citations"]
    else:
        assert "（修订）" in changed["spec"]["content_elements"][0]["text"]
        assert changed["citations"] != slide["citations"]
        for identity in slide["citations"].values():
            assert client.get(f"/api/citations/{identity}").json()["available"]
    assert state["image_calls"] == images + (action == "image")
    if action == "content":
        assert changed["assets"] == slide["assets"]
    unchanged_siblings(deck, updated, slide["id"])


@pytest.mark.parametrize(
    "instruction,target",
    [("减少文字", "content"), ("改变图片，使用抽象形状", "image"), ("更多留白", "visual")],
)
def test_natural_language_revision_selects_layer_and_inherits_style(revisions, instruction, target):
    client, state, _, deck, _ = revisions
    slide = deck["slides"][1]
    updated, job = submit(client, deck, slide, "revise", instruction)
    assert job["status"] == "completed", job
    with client.app.state.db.connect() as conn:
        record = conn.execute(
            "SELECT target,decision_json FROM slide_revisions WHERE slide_id=?", (slide["id"],)
        ).fetchone()
    assert record["target"] == target
    assert instruction in json.dumps(state["calls"], ensure_ascii=False)
    unchanged_siblings(deck, updated, slide["id"])


def test_failed_render_retry_resumes_saved_content_and_keeps_old_preview(revisions):
    client, state, renderer, deck, _ = revisions
    slide = deck["slides"][0]
    renderer.fail = True
    failed, job = submit(client, deck, slide, "content")
    assert job["status"] == "failed" and failed["status"] == "partial"
    changed = failed["slides"][0]
    assert changed["render"]["id"] == slide["render"]["id"] and not changed["render_current"]
    assert changed["revision"] == slide["revision"] + 1
    before = len(state["calls"])
    renderer.fail = False
    retry = client.post(f"/api/decks/{deck['id']}/slides/{slide['id']}/retry").json()
    assert retry["id"] == job["id"]
    assert wait_for_job(client, retry["id"])["status"] == "completed"
    updated = client.get(f"/api/decks/{deck['id']}").json()
    assert len(state["calls"]) == before
    assert updated["slides"][0]["spec"] == changed["spec"]
    assert updated["slides"][0]["revision"] == changed["revision"]
    assert updated["slides"][0]["render_current"]
    unchanged_siblings(deck, updated, slide["id"])


def test_interrupted_revision_recovers_applied_stage_without_reauthoring(revisions):
    from opennotelm.jobs import JobService
    from opennotelm.revisions import RevisionService

    client, state, renderer, deck, _ = revisions
    original_render = renderer.render

    async def interrupted(*args, **kwargs):
        raise asyncio.CancelledError()

    client.portal.call(client.app.state.jobs.stop)
    renderer.render = interrupted
    slide = deck["slides"][0]
    response = client.post(
        f"/api/decks/{deck['id']}/slides/{slide['id']}/revise",
        json={"revision": slide["revision"], "action": "content"},
    )

    async def run_until_interruption():
        try:
            await client.app.state.jobs.run_one()
        except asyncio.CancelledError:
            pass

    client.portal.call(run_until_interruption)
    saved = client.get(f"/api/decks/{deck['id']}").json()["slides"][0]
    assert saved["revision"] == slide["revision"] + 1 and not saved["render_current"]
    assert "（修订）" in saved["spec"]["content_elements"][0]["text"]
    before = len(state["calls"])
    renderer.render = original_render
    queue = JobService(client.app.state.db)
    RevisionService(client.app.state.db, queue, client.app.state.decks)
    client.portal.call(queue.run_one)
    assert queue.get(response.json()["id"])["status"] == "completed"
    updated = client.get(f"/api/decks/{deck['id']}").json()
    assert len(state["calls"]) == before
    assert updated["slides"][0]["spec"] == saved["spec"]
    assert updated["slides"][0]["render_current"]
    unchanged_siblings(deck, updated, slide["id"])


def test_failed_image_revision_can_continue_without_image(revisions):
    client, state, _, deck, _ = revisions
    slide = deck["slides"][1]
    state["fail_image"] = True
    failed, job = submit(client, deck, slide, "image")
    assert job["status"] == "failed" and failed["slides"][1]["assets"][0]["status"] == "failed"
    before = state["image_calls"]
    retry = client.post(f"/api/decks/{deck['id']}/slides/{slide['id']}/without-image").json()
    assert retry["id"] == job["id"]
    assert wait_for_job(client, retry["id"])["status"] == "completed"
    updated = client.get(f"/api/decks/{deck['id']}").json()
    assert updated["slides"][1]["assets"][0]["status"] == "skipped"
    assert updated["slides"][1]["render_current"] and state["image_calls"] == before
    unchanged_siblings(deck, updated, slide["id"])


def test_missing_original_blocks_content_revision_but_not_visual_or_manual_text(revisions):
    client, state, _, deck, source = revisions
    slide = deck["slides"][0]
    client.delete(f"/api/sources/{source}")
    before = len(state["calls"])
    failed, old_job = submit(client, deck, slide, "content")
    assert old_job["error_code"] == "CITATION_SOURCE_UNAVAILABLE"
    assert len(state["calls"]) == before and failed["slides"][0]["spec"] == slide["spec"]
    updated, job = submit(client, failed, failed["slides"][0], "visual")
    assert job["status"] == "completed"
    retried = client.post(f"/api/jobs/{old_job['id']}/retry").json()
    assert wait_for_job(client, retried["id"])["error_code"] == "SLIDE_CHANGED"
    assert client.get(f"/api/decks/{deck['id']}").json()["slides"] == updated["slides"]


def test_reorder_delete_and_conflicts_do_not_regenerate_pages(revisions):
    client, state, renderer, deck, _ = revisions
    before = len(state["calls"])
    order = [s["id"] for s in reversed(deck["slides"])]
    response = client.put(
        f"/api/decks/{deck['id']}/order", json={"revision": deck["revision"], "slide_ids": order}
    )
    assert response.status_code == 200
    updated = response.json()
    assert [s["id"] for s in updated["slides"]] == order
    assert [s["ordinal"] for s in updated["slides"]] == list(range(10))
    assert {s["render"]["id"] for s in updated["slides"]} == {
        s["render"]["id"] for s in deck["slides"]
    }
    assert (
        client.put(
            f"/api/decks/{deck['id']}/order",
            json={"revision": deck["revision"], "slide_ids": order},
        ).status_code
        == 409
    )
    assert (
        client.put(
            f"/api/decks/{deck['id']}/order",
            json={"revision": updated["revision"], "slide_ids": order[:-1] + [order[0]]},
        ).status_code
        == 400
    )
    for slide in updated["slides"]:
        response = client.request(
            "DELETE",
            f"/api/decks/{deck['id']}/slides/{slide['id']}",
            json={"revision": slide["revision"]},
        )
        assert response.status_code == 200
        remaining = response.json()["slides"]
        assert [s["ordinal"] for s in remaining] == list(range(len(remaining)))
    assert response.json()["slide_count"] == 0
    assert len(state["calls"]) == before and len(renderer.calls) == 10


def test_busy_and_fabricated_citations_cannot_overwrite_saved_content(revisions):
    client, state, _, deck, _ = revisions
    slide = deck["slides"][0]
    client.portal.call(client.app.state.jobs.stop)
    response = client.post(
        f"/api/decks/{deck['id']}/slides/{slide['id']}/revise",
        json={"revision": slide["revision"], "action": "content"},
    )
    assert response.status_code == 202
    assert (
        client.put(
            f"/api/decks/{deck['id']}/order",
            json={"revision": deck["revision"], "slide_ids": [s["id"] for s in deck["slides"]]},
        ).status_code
        == 409
    )
    state["bad_citations"] = True
    client.portal.call(client.app.state.jobs.run_one)
    job = client.get(f"/api/jobs/{response.json()['id']}").json()
    assert job["error_code"] == "DECK_PAGE_INVALID"
    saved = client.get(f"/api/decks/{deck['id']}").json()["slides"][0]
    assert saved["revision"] == slide["revision"] and saved["spec"] == slide["spec"]
    assert saved["citations"] == slide["citations"]
