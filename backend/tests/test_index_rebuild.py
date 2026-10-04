import asyncio
import hashlib
import json
import threading
import time

from opennotelm.embedding_identity import legacy_signature
from opennotelm.errors import AppError
from restart_support import restart
from test_chat import ask, messages
from test_chat import grounded as grounded
from test_models import config
from test_sources import import_book, wait_for_job

ENDPOINT = "/api/settings/models/embedding/indexes"


def ready(client, count=1):
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        value = client.get(ENDPOINT).json()
        if value["counts"].get("ready") == count:
            return value
        time.sleep(0.02)
    raise AssertionError(value)


def vectors(client, source_id):
    with client.app.state.db.connect() as conn:
        return [
            list(row)
            for row in conn.execute(
                "SELECT c.*,e.* FROM chunks c JOIN embeddings e ON e.chunk_id=c.id "
                "WHERE c.source_id=? ORDER BY c.ordinal",
                (source_id,),
            )
        ]


def test_switch_is_index_only_shared_source_and_citations_survive(grounded, settings, monkeypatch):
    client, state, _ = grounded
    notebook, source_id = import_book(client)
    ask(client, notebook["id"])
    citation_id = next(iter(messages(client, notebook["id"])[-1]["citations"].values()))
    citation = client.get(f"/api/citations/{citation_id}").json()
    blocks = client.get(f"/api/sources/{source_id}/blocks").json()
    nodes = client.get(f"/api/sources/{source_id}/nodes").json()
    originals = {
        str(p): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (settings.data_dir / "sources").rglob("*")
        if p.is_file()
    }
    another = client.post("/api/notebooks", json={"title": "Shared"}).json()
    client.post(f"/api/notebooks/{another['id']}/sources/{source_id}")
    # Even an old parser version must not cause an index rebuild to reparse.
    with client.app.state.db.connect() as conn:
        conn.execute("UPDATE sources SET parser_version='old-parser' WHERE id=?", (source_id,))

    def forbidden(*args, **kwargs):
        raise AssertionError("Index-only tasks must not parse or OCR")

    monkeypatch.setattr(client.app.state.sources.parser, "parse", forbidden)
    monkeypatch.setattr(client.app.state.sources.vision, "enrich", forbidden)
    response = client.post(
        "/api/settings/models/test", json=config("embedding", model_id="new-model")
    )
    assert response.status_code == 200
    result = ready(client)
    assert result["total"] == 1
    assert result["sources"][0]["job_id"]
    assert client.get(f"/api/sources/{source_id}/blocks").json() == blocks
    assert client.get(f"/api/sources/{source_id}/nodes").json() == nodes
    assert client.get(f"/api/citations/{citation_id}").json() == citation
    assert {
        str(p): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (settings.data_dir / "sources").rglob("*")
        if p.is_file()
    } == originals
    assert ask(client, notebook["id"])["status"] == "completed"
    assert (
        messages(client, notebook["id"])[-1]["metadata"]["retrieval"]["embedding_model"]
        == "new-model"
    )
    assert "secret-never-leak" not in json.dumps(result)
    assert state["calls"]


def test_same_model_and_key_rotation_skip_but_endpoint_change_rebuilds(grounded):
    client, _, _ = grounded
    _, source_id = import_book(client)
    before = vectors(client, source_id)
    for overrides in ({}, {"api_key": "rotated-test-key"}):
        assert (
            client.post(
                "/api/settings/models/test", json=config("embedding", **overrides)
            ).status_code
            == 200
        )
        assert client.get(ENDPOINT).json()["sources"][0]["job_id"] is None
        assert vectors(client, source_id) == before
    assert (
        client.post(
            "/api/settings/models/test",
            json=config("embedding", base_url="https://other.example/v1"),
        ).status_code
        == 200
    )
    ready(client)
    assert vectors(client, source_id) != before


def test_failure_retains_old_index_and_retry_only_failed(grounded, monkeypatch):
    client, _, _ = grounded
    _, source_id = import_book(client)
    before = vectors(client, source_id)
    original = client.app.state.models.gateway.embeddings
    failed = threading.Event()

    async def embed(model, key, texts):
        if texts != ["embedding capability probe"] and model.model_id == "new-model":
            # Capability testing uses a single short probe; identify real source content.
            if any("复利" in text or "耐心" in text for text in texts):
                failed.set()
                raise AppError("MODEL_TIMEOUT", "Synthetic test failure")
        return await original(model, key, texts)

    monkeypatch.setattr(client.app.state.models.gateway, "embeddings", embed)
    response = client.post(
        "/api/settings/models/test", json=config("embedding", model_id="new-model")
    )
    assert response.status_code == 200
    assert failed.wait(5)
    value = client.get(ENDPOINT).json()
    job = wait_for_job(client, value["sources"][0]["job_id"])
    assert job["status"] == "failed" and job["error_code"] == "MODEL_TIMEOUT"
    assert vectors(client, source_id) == before
    assert client.get(ENDPOINT).json()["counts"]["failed"] == 1
    monkeypatch.setattr(client.app.state.models.gateway, "embeddings", original)
    retried = client.post(ENDPOINT + "/rebuild", json={"mode": "failed"})
    assert retried.status_code == 202 and retried.json()["queued"] == 1
    ready(client)
    assert vectors(client, source_id) != before
    assert client.post(ENDPOINT + "/rebuild", json={"mode": "missing"}).json()["queued"] == 0


def test_forced_rebuild_and_interruption_recovery(grounded, settings, monkeypatch):
    client, _, transport = grounded
    _, source_id = import_book(client)
    before = vectors(client, source_id)
    started = threading.Event()

    async def blocked(*args):
        started.set()
        await asyncio.sleep(100)

    monkeypatch.setattr(client.app.state.models.gateway, "embeddings", blocked)
    result = client.post(ENDPOINT + "/rebuild", json={"mode": "all"}).json()
    job_id = result["sources"][0]["job_id"]
    assert result["queued"] == 1 and started.wait(5)
    assert client.post(ENDPOINT + "/rebuild", json={"mode": "all"}).json()["queued"] == 0
    assert vectors(client, source_id) == before
    with restart(client, settings, transport=transport) as restarted:
        ready(restarted)
        assert restarted.get(f"/api/jobs/{job_id}").json()["status"] == "completed"
        assert vectors(restarted, source_id) != before


def test_switch_during_rebuild_never_publishes_obsolete_vectors(grounded, monkeypatch):
    client, _, _ = grounded
    _, source_id = import_book(client)
    before = vectors(client, source_id)
    original = client.app.state.models.gateway.embeddings
    started, release = threading.Event(), threading.Event()

    async def delayed(model, key, texts):
        if model.model_id == "middle-model" and any("复利" in text for text in texts):
            started.set()
            while not release.is_set():
                await asyncio.sleep(0.01)
        return await original(model, key, texts)

    monkeypatch.setattr(client.app.state.models.gateway, "embeddings", delayed)
    client.post("/api/settings/models/test", json=config("embedding", model_id="middle-model"))
    assert started.wait(5)
    old_job = client.get(ENDPOINT).json()["sources"][0]["job_id"]
    assert (
        client.post(
            "/api/settings/models/test", json=config("embedding", model_id="final-model")
        ).status_code
        == 200
    )
    assert vectors(client, source_id) == before
    release.set()
    ready(client)
    job = client.get(f"/api/jobs/{old_job}").json()
    assert job["status"] == "completed"
    assert client.get(ENDPOINT).json()["sources"][0]["job_id"] == old_job
    with client.app.state.db.connect() as conn:
        assert {row[0] for row in conn.execute("SELECT model_id FROM embeddings")} == {
            "final-model"
        }


def test_legacy_indexes_survive_upgrade_and_unlinked_sources_are_not_sent(grounded):
    client, _, _ = grounded
    notebook, source_id = import_book(client)
    with client.app.state.db.connect() as conn:
        row = conn.execute("SELECT * FROM model_configs WHERE role='embedding'").fetchone()
        capabilities = json.loads(row["capabilities_json"])
        capabilities.pop("index_signature")
        conn.execute(
            "UPDATE model_configs SET capabilities_json=? WHERE role='embedding'",
            (json.dumps(capabilities),),
        )
        conn.execute(
            "UPDATE embeddings SET config_hash=?",
            (legacy_signature(row["model_id"], capabilities["dimensions"]),),
        )
    before = vectors(client, source_id)
    assert client.get(ENDPOINT).json()["counts"]["ready"] == 1
    assert client.post("/api/settings/models/test", json=config("embedding")).status_code == 200
    assert vectors(client, source_id) == before
    client.delete(f"/api/notebooks/{notebook['id']}/sources/{source_id}")
    assert (
        client.post(
            "/api/settings/models/test", json=config("embedding", model_id="other")
        ).status_code
        == 200
    )
    assert client.get(ENDPOINT).json()["total"] == 0
    assert vectors(client, source_id) == before


def test_rebuild_requires_config_and_valid_mode(client):
    assert client.get(ENDPOINT).json()["configured"] is False
    assert client.post(ENDPOINT + "/rebuild", json={}).status_code == 409
    assert client.post(ENDPOINT + "/rebuild", json={"mode": "invalid"}).status_code == 422


def test_dimension_change_replaces_vectors_with_new_dimensions(grounded, monkeypatch):
    client, _, _ = grounded
    _, source_id = import_book(client)
    original = client.app.state.models.gateway.embeddings

    async def embed(model, key, texts):
        if model.model_id == "three-dimensions":
            return [[1.0, 2.0, 3.0] for _ in texts]
        return await original(model, key, texts)

    monkeypatch.setattr(client.app.state.models.gateway, "embeddings", embed)
    response = client.post(
        "/api/settings/models/test", json=config("embedding", model_id="three-dimensions")
    )
    assert response.status_code == 200
    assert response.json()["capabilities"]["dimensions"] == 3
    ready(client)
    with client.app.state.db.connect() as conn:
        rows = conn.execute("SELECT dimensions,vector_json FROM embeddings").fetchall()
    assert rows and all(
        row["dimensions"] == 3 and len(json.loads(row["vector_json"])) == 3 for row in rows
    )
    assert vectors(client, source_id)


def test_queued_targets_update_in_place_and_respect_source_writer(grounded, monkeypatch):
    client, state, _ = grounded
    _, source_id = import_book(client)
    started, release = threading.Event(), threading.Event()

    async def writer(payload, context):
        started.set()
        while not release.is_set():
            await asyncio.sleep(0.01)

    monkeypatch.setitem(client.app.state.jobs.handlers, "source_ingest", writer)
    blocker = client.app.state.jobs.enqueue("source_ingest", source_id, {"source_id": source_id})
    assert started.wait(5)
    client.post("/api/settings/models/test", json=config("embedding", model_id="queued-old"))
    first = client.get(ENDPOINT).json()["sources"][0]
    assert first["state"] == "queued"
    assert (
        client.post(
            "/api/settings/models/test", json=config("embedding", model_id="queued-new")
        ).status_code
        == 200
    )
    second = client.get(ENDPOINT).json()["sources"][0]
    assert second["state"] == "queued" and second["job_id"] == first["job_id"]
    assert client.delete(f"/api/sources/{source_id}").status_code == 409
    release.set()
    assert wait_for_job(client, blocker["id"])["status"] == "completed"
    ready(client)
    assert all(
        call.get("model") != "queued-old" or call.get("input") == ["OpenNoteLM capability test"]
        for call in state["calls"]
        if "input" in call
    )


def test_same_name_recalculation_failure_does_not_use_old_vector_space(grounded, monkeypatch):
    client, _, _ = grounded
    notebook, source_id = import_book(client)
    before = vectors(client, source_id)
    previous_hash = client.app.state.retrieval.embedding_config()[3]

    async def failed(*args):
        raise AppError("MODEL_TIMEOUT", "Synthetic changed-weight failure")

    monkeypatch.setattr(client.app.state.models.gateway, "embeddings", failed)
    result = client.post(ENDPOINT + "/rebuild", json={"mode": "all"}).json()
    assert result["queued"] == 1
    assert wait_for_job(client, result["sources"][0]["job_id"])["status"] == "failed"
    assert vectors(client, source_id) == before
    assert client.app.state.retrieval.embedding_config()[3] != previous_hash
    assert ask(client, notebook["id"])["error_code"] == "SOURCE_INDEX_REQUIRED"


def test_relinking_a_detached_source_rebuilds_only_its_stale_index(grounded, monkeypatch):
    client, _, _ = grounded
    notebook, source_id = import_book(client)
    blocks = client.get(f"/api/sources/{source_id}/blocks").json()
    assert client.delete(f"/api/notebooks/{notebook['id']}/sources/{source_id}").status_code == 204
    assert (
        client.post(
            "/api/settings/models/test", json=config("embedding", model_id="replacement")
        ).status_code
        == 200
    )
    assert client.get(ENDPOINT).json()["total"] == 0

    def forbidden(*args, **kwargs):
        raise AssertionError("Relinking must not parse or OCR")

    monkeypatch.setattr(client.app.state.sources.parser, "parse", forbidden)
    monkeypatch.setattr(client.app.state.sources.vision, "enrich", forbidden)
    client.portal.call(client.app.state.jobs.stop)
    for _ in range(2):
        assert (
            client.post(f"/api/notebooks/{notebook['id']}/sources/{source_id}").status_code == 200
        )
    with client.app.state.db.connect() as conn:
        jobs = conn.execute(
            "SELECT id FROM jobs WHERE type='source_reindex' AND status='queued'"
        ).fetchall()
    assert len(jobs) == 1
    assert client.portal.call(client.app.state.jobs.run_one)
    assert client.get(ENDPOINT).json()["counts"]["ready"] == 1
    assert client.get(f"/api/sources/{source_id}/blocks").json() == blocks
    client.portal.call(client.app.state.jobs.start)
    assert ask(client, notebook["id"])["status"] == "completed"
