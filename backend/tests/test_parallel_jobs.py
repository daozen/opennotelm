import asyncio
import json
import threading
from dataclasses import replace

import httpx
import pytest
from image_factory import image_response
from opennotelm.chunking import Chunk, Span
from opennotelm.db import Database
from opennotelm.errors import AppError
from opennotelm.gateway import ModelGateway
from opennotelm.generation_attempts import JOB_DIAGNOSTICS
from opennotelm.jobs import JobService
from opennotelm.request_limits import ProviderBudgets, SharedStageBudget
from opennotelm.schemas import ModelInput
from restart_support import restart
from test_knowledge import import_text
from test_models import config
from test_sources import wait_for_job


def test_queue_overlaps_entities_bounds_tasks_and_joins_stop_then_recovers(tmp_path):
    db = Database(tmp_path / "app.db")
    db.migrate()
    queue = JobService(db, concurrency=lambda: 3)

    async def run():
        entered, release = asyncio.Event(), asyncio.Event()
        active = set()
        peak = 0

        async def handler(payload, context):
            nonlocal peak
            entity = context.job["entity_id"]
            assert entity not in active
            active.add(entity)
            peak = max(peak, len(active))
            if len(active) == 3:
                entered.set()
            try:
                await release.wait()
                return {"value": payload["value"]}
            finally:
                await asyncio.sleep(0.01)
                active.remove(entity)

        queue.handlers.update(first=handler, second=handler)
        jobs = [queue.enqueue("first", str(i), {"value": i}) for i in range(5)]
        sibling = queue.enqueue("second", "0", {"value": 99})
        queue.start()
        await asyncio.wait_for(entered.wait(), 2)
        assert sum(queue.get(j["id"])["status"] == "running" for j in jobs) == 3
        await queue.cancel_entity("0")
        assert "0" not in active
        # The other two tasks survive stopping one entity.
        assert {"1", "2"} <= active
        await queue.stop()
        assert not active and peak == 3
        assert queue.get(jobs[0]["id"])["status"] == "cancelled"
        assert queue.get(sibling["id"])["status"] == "cancelled"
        release.set()
        queue.start()
        for _ in range(100):
            if all(queue.get(j["id"])["status"] == "completed" for j in jobs[1:]):
                break
            await asyncio.sleep(0.01)
        await queue.stop()
        assert all(queue.get(j["id"])["result"] == {"value": i} for i, j in enumerate(jobs) if i)
        assert queue.get(jobs[0]["id"])["status"] == "cancelled"

    asyncio.run(run())


def test_multiple_uploaded_files_parse_concurrently_without_mixing_originals(client):
    parser = client.app.state.sources.parsers["text"][1]
    original = parser.parse
    entered, release = threading.Event(), threading.Event()
    lock = threading.Lock()
    active = peak = 0

    def parse(*args):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
            if active == 3:
                entered.set()
        try:
            assert release.wait(3)
            return original(*args)
        finally:
            with lock:
                active -= 1

    parser.parse = parse
    notebook = client.post("/api/notebooks", json={"title": "Parallel files"}).json()["id"]
    results = []
    try:
        for i in range(3):
            results.append(
                client.post(
                    f"/api/notebooks/{notebook}/sources/upload",
                    files={"file": (f"{i}.txt", f"Original paragraph {i}".encode())},
                ).json()
            )
        assert entered.wait(2) and peak == 3
    finally:
        release.set()
    for i, result in enumerate(results):
        assert wait_for_job(client, result["job"]["id"])["status"] == "completed"
        blocks = client.get(f"/api/sources/{result['source']['id']}/blocks").json()
        assert blocks[0]["text"] == f"Original paragraph {i}"
    assert active == 0


def test_shared_stage_budget_bounds_cross_job_preparation_and_preserves_snapshots():
    async def run():
        budget = SharedStageBudget()
        release, entered = asyncio.Event(), asyncio.Event()
        active = peak = 0

        async def prepare(owner):
            nonlocal active, peak
            token = JOB_DIAGNOSTICS.set((None, owner))
            try:
                async with budget.slot(2):
                    active += 1
                    peak = max(peak, active)
                    if active == 2:
                        entered.set()
                    try:
                        await release.wait()
                    finally:
                        active -= 1
            finally:
                JOB_DIAGNOSTICS.reset(token)

        tasks = [asyncio.create_task(prepare(str(i))) for i in range(8)]
        await entered.wait()
        assert active == 2
        tasks[-1].cancel()
        release.set()
        await asyncio.gather(*tasks, return_exceptions=True)
        assert peak == 2 and active == 0 and not budget.leases
        async with budget.slot(4):
            async with budget.slot(1):
                assert budget.budget.limit() == 4
            assert budget.budget.limit() == 4
        assert budget.budget.active == 0

    asyncio.run(run())


def test_claim_serializes_same_entity_and_source_writers_but_allows_shared_readers(tmp_path):
    db = Database(tmp_path / "app.db")
    db.migrate()
    queue = JobService(db)
    with db.connect() as conn:
        for identity in ("source", "other-source"):
            conn.execute(
                "INSERT INTO sources(id,type,title,original_filename,mime_type,file_uri,"
                "file_size,checksum_sha256,created_at,updated_at) "
                "VALUES (?,'text',?,'sample.txt','text/plain','unused',1,?,'now','now')",
                (identity, identity, identity),
            )
    read = queue.enqueue("test", "deck-a", {"scope": {"source_id": "source"}})
    sibling = queue.enqueue("revision", "deck-a", {})
    reader = queue.enqueue("test", "deck-b", {"scope": {"source_id": "source"}})
    writer = queue.enqueue("source_ingest", "source", {})
    late_reader = queue.enqueue("test", "deck-c", {"scope": {"source_id": "source"}})
    unrelated = queue.enqueue("source_ingest", "other-source", {})
    assert queue.claim()["id"] == read["id"]
    assert {queue.claim()["id"], queue.claim()["id"]} == {reader["id"], unrelated["id"]}
    assert queue.claim() is None
    with db.connect() as conn:
        conn.execute("UPDATE jobs SET status='completed' WHERE status='running'")
    assert {queue.claim()["id"], queue.claim()["id"]} == {sibling["id"], writer["id"]}
    assert queue.get(late_reader["id"])["status"] == "queued"


def test_task_families_rotate_without_starving_interactive_tasks_behind_batches(tmp_path):
    db = Database(tmp_path / "app.db")
    db.migrate()
    queue = JobService(db)
    for kind in ("source_custom", "deck_generate", "chat_answer"):
        for i in range(3):
            queue.enqueue(kind, f"{kind}-{i}", {})
    assert [queue.group(queue.claim()) for _ in range(9)] == ["source", "deck", "interactive"] * 3


def test_provider_budget_is_fair_cancellable_resizable_and_origin_shared():
    async def run():
        limit = 1
        budgets = ProviderBudgets(lambda: limit)
        a = ModelInput(base_url="http://localhost:8317/v1", model_id="a")
        b = ModelInput(base_url="http://LOCALHOST:8317/other", model_id="b")
        entered, release = asyncio.Event(), asyncio.Event()
        order = []

        async def request(owner, number, hold=False):
            token = JOB_DIAGNOSTICS.set((None, owner))
            try:
                async with budgets.slot(a if owner == "a" else b):
                    order.append((owner, number))
                    if hold:
                        entered.set()
                        await release.wait()
            finally:
                JOB_DIAGNOSTICS.reset(token)

        leader = asyncio.create_task(request("a", 0, True))
        await entered.wait()
        tasks = [asyncio.create_task(request("a", i)) for i in range(1, 5)]
        follower = asyncio.create_task(request("b", 1))
        cancelled = asyncio.create_task(request("cancel", 1))
        await asyncio.sleep(0)
        cancelled.cancel()
        await asyncio.gather(cancelled, return_exceptions=True)
        release.set()
        await asyncio.gather(leader, *tasks, follower)
        assert order.index(("b", 1)) < order.index(("a", 3))
        assert all(owner != "cancel" for owner, _ in order)
        budget = next(iter(budgets.providers.values()))
        assert len(budgets.providers) == 1 and budget.active == 0 and not budget.waiters
        # A grant followed immediately by cancellation must release its reservation.
        task = asyncio.create_task(request("a", 10))
        await asyncio.sleep(0)
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        assert budget.active == 0
        limit = 2
        async with budgets.slot(a), budgets.slot(b):
            assert budget.active == 2
            limit = 1
            waiting = asyncio.create_task(request("a", 11))
            await asyncio.sleep(0)
            assert not waiting.done()
        await waiting
        assert budget.active == 0

    asyncio.run(run())


def test_gateway_text_embeddings_and_images_share_one_provider_budget():
    async def run():
        active = peak = 0

        async def handler(request):
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            try:
                await asyncio.sleep(0.02)
                if request.url.path.endswith("/images/generations"):
                    return httpx.Response(200, json=image_response())
                if request.url.path.endswith("/embeddings"):
                    return httpx.Response(200, json={"data": [{"index": 0, "embedding": [1, 2]}]})
                return httpx.Response(200, json={"choices": [{"message": {"content": "OK"}}]})
            finally:
                active -= 1

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            gateway = ModelGateway(client, lambda: 2)
            config = ModelInput(base_url="https://example.com/v1", model_id="fake")
            await asyncio.gather(
                gateway.text(config, "", []),
                gateway.embeddings(config, "", ["sample"]),
                gateway.images.generate(config, "", "sample"),
                gateway.text(config, "", []),
            )
        assert peak == 2 and active == 0

    asyncio.run(run())


def test_embedding_batches_overlap_keep_order_and_publish_atomically(client, monkeypatch):
    client.post("/api/settings/models/test", json=config("embedding"))
    notebook = client.post("/api/notebooks", json={"title": "Index concurrency"}).json()["id"]
    source = import_text(client, notebook, "A stable original paragraph.", "index.txt")
    db = client.app.state.db
    with db.connect() as conn:
        before = [
            tuple(row) for row in conn.execute("SELECT * FROM chunks WHERE source_id=?", (source,))
        ]
        block = dict(
            conn.execute("SELECT * FROM content_blocks WHERE source_id=?", (source,)).fetchone()
        )
        conn.execute("UPDATE embeddings SET config_hash='old' WHERE chunk_id=?", (before[0][0],))
    chunks = [
        Chunk(
            f"chunk-{i}",
            source,
            block["node_id"],
            i,
            str(i),
            [Span(block["id"], 0, len(block["text"]), block["text"])],
        )
        for i in range(65)
    ]
    monkeypatch.setattr("opennotelm.retrieval.make_chunks", lambda *args: chunks)
    active = peak = 0
    fail = True

    async def embeddings(config, key, texts):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        try:
            await asyncio.sleep(0.01 if texts[0] == "32" else 0.04)
            if fail and texts[0] == "64":
                raise AppError("MODEL_TIMEOUT", "Safe test failure")
            return [[1.0, float(int(text) + 1)] for text in texts]
        finally:
            active -= 1

    monkeypatch.setattr(client.app.state.models.gateway, "embeddings", embeddings)

    class Context:
        def progress(self, *args):
            pass

    with pytest.raises(AppError):
        client.portal.call(client.app.state.retrieval.index, source, Context())
    with db.connect() as conn:
        assert [
            tuple(row) for row in conn.execute("SELECT * FROM chunks WHERE source_id=?", (source,))
        ] == before
    fail = False
    assert client.portal.call(client.app.state.retrieval.index, source, Context())["indexed"]
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT c.ordinal,e.vector_json FROM chunks c JOIN embeddings e "
            "ON e.chunk_id=c.id WHERE c.source_id=? ORDER BY c.ordinal",
            (source,),
        ).fetchall()
    assert peak == 2 and active == 0 and len(rows) == 65
    for i, row in enumerate(rows):
        vector = json.loads(row["vector_json"])
        assert row["ordinal"] == i and vector[1] / vector[0] == pytest.approx(i + 1)


@pytest.mark.parametrize("name,default,maximum", [("task", 3, 8), ("request", 8, 20)])
def test_admission_settings_are_strict_persistent_and_model_independent(
    client, settings, provider, name, default, maximum
):
    path = f"/api/settings/models/{name}-concurrency"
    assert client.get(path).json() == {
        "concurrency": default,
        "min_concurrency": 1,
        "max_concurrency": maximum,
    }
    for invalid in (0, maximum + 1, True, "3", 2.5):
        assert client.put(path, json={"concurrency": invalid}).status_code == 422
    assert client.put(path, json={"concurrency": maximum}).json()["concurrency"] == maximum
    with restart(client, replace(settings), provider[0]) as app:
        assert app.get(path).json()["concurrency"] == maximum
    assert not provider[1]
