import json
from unittest.mock import patch

import pytest
from document_factory import make_pdf
from docx_factory import make_docx
from epub_factory import make_epub
from opennotelm.decks import DeckService
from opennotelm.retrieval import Scope
from restart_support import restart
from test_decks import decks, notebook_with_source  # noqa: F401
from test_knowledge import import_text
from test_sources import wait_for_job


def post_batch(client, notebook, scope, key="batch-request-01", **options):
    return client.post(
        f"/api/notebooks/{notebook}/decks/batch",
        json={
            "request_key": key,
            "scope": scope,
            "slide_count": 10,
            "render_mode": "native",
            **options,
        },
    )


@pytest.mark.parametrize("format", ["epub", "pdf", "docx"])
def test_separate_chapters_generate_independent_scopes_and_citations(decks, format):  # noqa: F811
    client, _, _ = decks
    notebook = client.post("/api/notebooks", json={"title": "Separate"}).json()["id"]
    result = client.post(
        f"/api/notebooks/{notebook}/sources/upload",
        files={
            "file": (
                "book." + format,
                {"epub": make_epub, "pdf": make_pdf, "docx": make_docx}[format](),
            )
        },
    ).json()
    assert wait_for_job(client, result["job"]["id"])["status"] == "completed"
    source = result["source"]["id"]
    nodes = client.get(f"/api/sources/{source}/nodes").json()
    chapters = [n for n in nodes if n["type"] == ("heading" if format == "docx" else "chapter")]
    requested = [chapters[1]["id"], chapters[0]["id"], chapters[0]["id"]]
    child = next((n for n in nodes if n["parent_id"] == chapters[0]["id"]), None)
    if child:
        requested.append(child["id"])
    response = post_batch(
        client,
        notebook,
        {"kind": "nodes", "source_id": source, "node_ids": requested},
        title_mode="source",
    )
    assert response.status_code == 202, response.text
    batch = response.json()
    assert len(batch["decks"]) == 2
    for index, created in enumerate(batch["decks"]):
        assert created["source_scope"]["node_id"] == chapters[index]["id"]
        assert wait_for_job(client, created["job"]["id"])["status"] == "completed"
        deck = client.get(f"/api/decks/{created['id']}").json()
        manifest = client.get(f"/api/decks/{created['id']}/sources").json()
        entry = manifest["sources"][0]
        chapter = entry["chapters"][0]
        assert deck["title"] == f"{entry['title']}-{chapter['number']}-{chapter['title']}"
        expected = client.app.state.retrieval.scope_blocks(
            notebook, Scope(**created["source_scope"])
        )
        assert deck["generation_metadata"]["block_ids"] == [b["id"] for b in expected]
        assert deck["generation_metadata"]["batch_id"] == batch["batch_id"]
        assert deck["generation_metadata"]["batch_index"] == index
        assert deck["generation_metadata"]["batch_size"] == 2
        assert len(deck["slides"]) == 10
        for slide in deck["slides"]:
            for ref in slide["citations"].values():
                citation = client.get(f"/api/citations/{ref}").json()
                assert all(
                    span["block_id"] in deck["generation_metadata"]["block_ids"]
                    for span in citation["spans"]
                )
    first, second = [client.get(f"/api/decks/{d['id']}").json() for d in batch["decks"]]
    assert not set(first["generation_metadata"]["block_ids"]) & set(
        second["generation_metadata"]["block_ids"]
    )


def test_source_batch_is_frozen_ordered_and_idempotent_across_restart(decks, settings):  # noqa: F811
    client, state, transport = decks
    notebook, first = notebook_with_source(client)
    second = import_text(client, notebook, "SECOND_SOURCE: patient practice supports learning.")
    client.portal.call(client.app.state.jobs.stop)
    scope = {"kind": "selected", "source_ids": [second, first]}
    response = post_batch(client, notebook, scope)
    assert response.status_code == 202, response.text
    batch = response.json()
    assert [d["source_scope"]["source_id"] for d in batch["decks"]] == [first, second]
    assert all(d["job"]["status"] == "queued" for d in batch["decks"])
    before = len(state["calls"])
    assert post_batch(client, notebook, scope).json() == batch
    assert len(state["calls"]) == before
    assert post_batch(client, notebook, scope, slide_count=20).status_code == 409
    for source in [first, second]:
        client.patch(f"/api/notebooks/{notebook}/sources/{source}", json={"enabled": False})
    claimed = client.app.state.jobs.claim()
    assert claimed["id"] == batch["decks"][0]["job"]["id"]
    generate = DeckService.generate

    async def content_only(service, payload, context):
        service.composition = service.assets = service.exports = None
        return await generate(service, payload, context)

    with (
        patch.object(DeckService, "generate", content_only),
        restart(client, settings, transport) as restarted,
    ):
        for created in batch["decks"]:
            assert wait_for_job(restarted, created["job"]["id"])["status"] == "completed"
        repeated = post_batch(restarted, notebook, scope).json()
        assert repeated["batch_id"] == batch["batch_id"]
        assert [d["id"] for d in repeated["decks"]] == [d["id"] for d in batch["decks"]]
        assert all(d["status"] == "draft" and len(d["slides"]) == 10 for d in repeated["decks"])
        assert len(restarted.get(f"/api/notebooks/{notebook}/decks").json()) == 2


def test_failed_sibling_can_retry_without_recreating_completed_decks(decks):  # noqa: F811
    client, state, _ = decks
    notebook, _ = notebook_with_source(client)
    import_text(client, notebook, "Second chapter: steady practice helps.")
    client.portal.call(client.app.state.jobs.stop)
    batch = post_batch(client, notebook, {"kind": "selected"}).json()
    state["bad_plan"] = True
    client.portal.call(client.app.state.jobs.run_one)
    failed = client.get(f"/api/decks/{batch['decks'][0]['id']}").json()
    assert failed["job"]["status"] == "failed"
    state["bad_plan"] = False
    client.portal.call(client.app.state.jobs.run_one)
    sibling = client.get(f"/api/decks/{batch['decks'][1]['id']}").json()
    assert sibling["job"]["status"] == "completed"
    assert client.post(f"/api/decks/{failed['id']}/retry").status_code == 202
    client.portal.call(client.app.state.jobs.run_one)
    assert client.get(f"/api/decks/{failed['id']}").json()["job"]["status"] == "completed"
    assert client.get(f"/api/decks/{sibling['id']}").json() == sibling
    assert len(client.get(f"/api/notebooks/{notebook}/decks").json()) == 2


def test_batch_validation_and_transaction_failure_leave_no_partial_work(decks, monkeypatch):  # noqa: F811
    client, state, _ = decks
    notebook, first = notebook_with_source(client)
    second = import_text(client, notebook, "Second source: clear explanations support learning.")
    client.portal.call(client.app.state.jobs.stop)
    invalid = [
        {"kind": "nodes", "source_id": first, "node_ids": ["foreign"]},
        {"kind": "nodes", "source_id": first, "node_ids": []},
        {"kind": "selected", "source_ids": []},
        {"kind": "selected", "source_ids": [first, "foreign"]},
    ]
    before = len(state["calls"])
    for scope in invalid:
        assert post_batch(client, notebook, scope).status_code in (400, 422)
    monkeypatch.setattr("opennotelm.decks.MAX_BATCH_DECKS", 1)
    assert (
        post_batch(client, notebook, {"kind": "selected"}).json()["error"]["code"]
        == "DECK_BATCH_LIMIT"
    )
    monkeypatch.setattr("opennotelm.decks.MAX_BATCH_DECKS", 100)
    enqueue = client.app.state.jobs.enqueue_in_transaction
    calls = []

    def fail_second(conn, kind, identity, payload):
        calls.append(identity)
        if len(calls) == 2:
            raise RuntimeError("Simulated interrupted batch insertion")
        return enqueue(conn, kind, identity, payload)

    with patch.object(client.app.state.jobs, "enqueue_in_transaction", fail_second):
        with pytest.raises(RuntimeError, match="interrupted batch"):
            post_batch(client, notebook, {"kind": "selected"})
    with client.app.state.db.connect() as conn:
        assert conn.execute("SELECT count(*) FROM decks").fetchone()[0] == 0
        assert conn.execute("SELECT count(*) FROM deck_batches").fetchone()[0] == 0
        assert (
            conn.execute("SELECT count(*) FROM jobs WHERE type='deck_generate'").fetchone()[0] == 0
        )
        assert not conn.execute("PRAGMA foreign_key_check").fetchall()
    assert len(state["calls"]) == before
    with client.app.state.db.connect() as conn:
        conn.execute("UPDATE content_blocks SET text='' WHERE source_id=?", (second,))
    assert (
        post_batch(client, notebook, {"kind": "selected"}).json()["error"]["code"]
        == "SOURCE_NO_TEXT"
    )
    assert client.get(f"/api/notebooks/{notebook}/decks").json() == []


def test_batch_deleted_with_notebook_and_no_credentials_in_snapshot(decks):  # noqa: F811
    client, _, _ = decks
    notebook, _ = notebook_with_source(client)
    client.portal.call(client.app.state.jobs.stop)
    batch = post_batch(client, notebook, {"kind": "selected"}).json()
    with client.app.state.db.connect() as conn:
        row = dict(
            conn.execute("SELECT * FROM deck_batches WHERE id=?", (batch["batch_id"],)).fetchone()
        )
        assert "api_key" not in json.dumps(row)
    assert client.delete(f"/api/notebooks/{notebook}").status_code == 409
    client.portal.call(client.app.state.jobs.run_one)
    assert client.delete(f"/api/notebooks/{notebook}").status_code == 204
    with client.app.state.db.connect() as conn:
        assert conn.execute("SELECT count(*) FROM deck_batches").fetchone()[0] == 0
        assert conn.execute("SELECT count(*) FROM decks").fetchone()[0] == 0
