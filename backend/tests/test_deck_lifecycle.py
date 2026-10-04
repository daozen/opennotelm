import asyncio
import copy
import threading

from restart_support import restart
from test_deck_batches import post_batch
from test_decks import decks, notebook_with_source  # noqa: F401
from test_revisions import revisions  # noqa: F401
from test_sources import wait_for_job


def test_queued_stop_resume_is_idempotent_and_remains_stopped_after_restart(decks, settings):  # noqa: F811
    client, _, transport = decks
    notebook, source = notebook_with_source(client)
    client.portal.call(client.app.state.jobs.stop)
    batch = post_batch(client, notebook, {"kind": "source", "source_id": source}).json()
    original = batch["decks"][0]
    identity = original["id"]
    job_id = original["job"]["id"]
    stopped = client.post(f"/api/decks/{identity}/stop").json()
    assert stopped["status"] == "paused"
    assert stopped["job"]["id"] == job_id and stopped["job"]["status"] == "cancelled"
    assert client.post(f"/api/decks/{identity}/stop").json() == stopped
    assert client.get(f"/api/notebooks/{notebook}/decks").json()[0]["status"] == "paused"
    with restart(client, settings, transport) as restarted:
        assert restarted.get(f"/api/decks/{identity}").json()["job"]["status"] == "cancelled"
        restarted.portal.call(restarted.app.state.jobs.stop)
        resumed = restarted.post(f"/api/decks/{identity}/resume").json()
        assert resumed["job"]["id"] == job_id
        assert resumed["job"]["payload"] == original["job"]["payload"]
        assert resumed["job"]["status"] == "queued"
        assert restarted.post(f"/api/decks/{identity}/resume").json()["job"]["id"] == job_id
        assert restarted.delete(f"/api/decks/{identity}").status_code == 204
        assert restarted.get(f"/api/jobs/{job_id}").status_code == 404
        assert restarted.get(f"/api/sources/{source}").status_code == 200
        assert restarted.delete(f"/api/decks/{identity}").status_code == 204
        # Old batch receipts cannot silently recreate deleted Decks.
        assert (
            post_batch(restarted, notebook, {"kind": "source", "source_id": source}).status_code
            == 409
        )


def test_running_stop_preserves_authored_pages_and_resumes_without_reauthoring(decks):  # noqa: F811
    client, state, _ = decks
    notebook, source = notebook_with_source(client)
    entered, exited = threading.Event(), threading.Event()
    service = client.app.state.decks
    original_author = service.author
    count = 0

    client.put("/api/settings/models/content-generation", json={"concurrency": 1})

    async def block_fourth(*args, **kwargs):
        nonlocal count
        count += 1
        if count == 4:
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                exited.set()
        return await original_author(*args, **kwargs)

    service.author = block_fourth
    created = client.post(
        f"/api/notebooks/{notebook}/decks",
        json={"slide_count": 10, "scope": {"kind": "selected"}, "render_mode": "native"},
    ).json()
    identity, job_id = created["id"], created["job"]["id"]
    assert entered.wait(5)
    before = client.get(f"/api/decks/{identity}").json()
    saved = [s for s in before["slides"] if s["spec"]]
    assert len(saved) == 3
    stopped = client.post(f"/api/decks/{identity}/stop").json()
    assert exited.is_set()
    assert stopped["status"] == "paused" and stopped["job"]["status"] == "cancelled"
    assert stopped["slides"] == before["slides"]
    assert stopped["plan"] == before["plan"] and stopped["style"] == before["style"]
    service.author = original_author
    resumed = client.post(f"/api/decks/{identity}/resume").json()
    assert resumed["job"]["id"] == job_id
    assert wait_for_job(client, job_id)["status"] == "completed"
    finished = client.get(f"/api/decks/{identity}").json()
    assert all(s["spec"] for s in finished["slides"])
    assert finished["slides"][:3] == saved
    authors = [
        c
        for c in state["calls"]
        if c.get("messages", [{}])[0].get("content", "").startswith("Author one SlideSpec")
    ]
    assert len(authors) == 10
    assert client.post(f"/api/decks/{identity}/resume").status_code == 409
    assert client.get(f"/api/sources/{source}").status_code == 200


def test_delete_completed_deck_removes_all_versions_jobs_citations_and_owned_files(revisions):  # noqa: F811
    client, _, _, deck, source = revisions
    root = client.app.state.sources.settings.data_dir
    before = copy.deepcopy(deck)
    with client.app.state.db.connect() as conn:
        owned = [
            root / prefix / row[0]
            for table, prefix in [("assets", "assets"), ("slide_renders", "renders")]
            for row in conn.execute(f"SELECT id FROM {table}")
        ]
        # An interrupted export version is owned by this Deck too.
        conn.execute(
            "INSERT INTO pdf_exports(id,deck_id,input_hash,status,created_at,updated_at) VALUES ('"
            + "a" * 32
            + "',?,'old','failed','then','then')",
            (deck["id"],),
        )
        export = root / "exports" / ("a" * 32)
        export.mkdir()
        (export / "deck.pdf").write_bytes(b"old-export")
        owned.append(export)
    assert client.delete(f"/api/decks/{deck['id']}").status_code == 204
    assert client.get(f"/api/decks/{deck['id']}").status_code == 404
    assert all(not path.exists() for path in owned)
    with client.app.state.db.connect() as conn:
        for table in [
            "decks",
            "slides",
            "slide_designs",
            "assets",
            "slide_renders",
            "pdf_exports",
            "slide_revisions",
            "citations",
            "citation_spans",
            "garbage_files",
        ]:
            assert conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 0
        assert not conn.execute("SELECT 1 FROM jobs WHERE entity_id=?", (deck["id"],)).fetchone()
        assert not conn.execute("PRAGMA foreign_key_check").fetchone()
    assert client.get(f"/api/sources/{source}").status_code == 200
    assert before["slides"]


def test_delete_running_deck_waits_for_work_and_leaves_next_deck_intact(decks):  # noqa: F811
    client, _, _ = decks
    notebook, source = notebook_with_source(client)
    entered, exited = threading.Event(), threading.Event()
    service = client.app.state.decks
    original_author = service.author
    blocked_id = None

    async def block(deck, *args, **kwargs):
        if deck["id"] == blocked_id:
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                exited.set()
        return await original_author(deck, *args, **kwargs)

    service.author = block
    client.portal.call(client.app.state.jobs.stop)
    created = client.post(
        f"/api/notebooks/{notebook}/decks",
        json={"slide_count": 10, "scope": {"kind": "selected"}, "render_mode": "native"},
    ).json()
    blocked_id = created["id"]
    sibling = client.post(
        f"/api/notebooks/{notebook}/decks",
        json={"slide_count": 10, "scope": {"kind": "selected"}, "render_mode": "native"},
    ).json()
    client.portal.call(client.app.state.jobs.start)
    assert entered.wait(5)
    assert client.delete(f"/api/decks/{blocked_id}").status_code == 204
    assert exited.is_set()
    assert client.get(f"/api/jobs/{created['job']['id']}").status_code == 404
    assert wait_for_job(client, sibling["job"]["id"])["status"] == "completed"
    assert client.get(f"/api/decks/{sibling['id']}").json()["slides"]
    assert client.get(f"/api/sources/{source}").status_code == 200
