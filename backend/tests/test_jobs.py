import asyncio

import pytest
from opennotelm.db import Database
from opennotelm.errors import AppError
from opennotelm.jobs import JobService


def test_durable_retry_deduplication_and_progress(tmp_path):
    db = Database(tmp_path / "app.db")
    db.migrate()
    queue = JobService(db)
    calls = 0

    async def handler(payload, context):
        nonlocal calls
        calls += 1
        context.progress("test-stage", 0.5)
        if calls == 1:
            raise AppError("TEST_FAILED", "Safe failure")
        return {"preserved_input": payload["number"]}

    queue.handlers["test"] = handler
    job = queue.enqueue("test", "entity", {"number": 5})
    assert queue.enqueue("test", "entity", {"number": 9})["id"] == job["id"]
    assert asyncio.run(queue.run_one())
    assert queue.get(job["id"])["error_code"] == "TEST_FAILED"
    assert queue.get(job["id"])["stage"] == "test-stage"
    restarted = JobService(db)
    restarted.handlers["test"] = handler
    assert restarted.retry(job["id"])["retry_count"] == 1
    assert asyncio.run(restarted.run_one())
    finished = restarted.get(job["id"])
    assert finished["status"] == "completed"
    assert finished["result"]["preserved_input"] == 5
    assert finished["progress"] == 1
    with pytest.raises(AppError):
        restarted.retry(job["id"])


def test_interrupted_running_job_recovers(tmp_path):
    db = Database(tmp_path / "app.db")
    db.migrate()
    queue = JobService(db)
    job = queue.enqueue("test", "entity", {})
    queue.claim()
    assert queue.get(job["id"])["status"] == "running"

    async def scenario():
        restarted = JobService(db)
        complete = asyncio.Event()

        async def handler(payload, context):
            complete.set()
            return {"recovered": True}

        restarted.handlers["test"] = handler
        restarted.start()
        await asyncio.wait_for(complete.wait(), timeout=2)
        await restarted.stop()
        return restarted.get(job["id"])

    assert asyncio.run(scenario())["status"] == "completed"


def test_retry_cannot_interleave_with_another_layer_of_the_same_entity(tmp_path):
    db = Database(tmp_path / "app.db")
    db.migrate()
    queue = JobService(db)
    failed = queue.enqueue("deck_generate", "deck", {})
    asyncio.run(queue.run_one())
    active = queue.enqueue("slide_revision", "deck", {})
    with pytest.raises(AppError, match="ENTITY_BUSY"):
        queue.retry(failed["id"])
    assert queue.get(failed["id"])["status"] == "failed"
    assert queue.get(active["id"])["status"] == "queued"


def test_equal_timestamp_jobs_keep_insertion_order_after_restart(tmp_path, monkeypatch):
    from types import SimpleNamespace

    db = Database(tmp_path / "app.db")
    db.migrate()
    ids = iter(["f" * 32, "a" * 32])
    monkeypatch.setattr("opennotelm.jobs.uuid4", lambda: SimpleNamespace(hex=next(ids)))
    monkeypatch.setattr("opennotelm.jobs.now", lambda: "2026-10-03T00:00:00+00:00")
    queue = JobService(db)
    first = queue.enqueue("test", "first-section", {})
    second = queue.enqueue("test", "second-section", {})
    resumed = JobService(db)
    assert resumed.claim()["id"] == first["id"]
    assert resumed.claim()["id"] == second["id"]


def test_cancel_joins_parallel_work_keeps_worker_alive_and_does_not_resume_on_restart(tmp_path):
    db = Database(tmp_path / "app.db")
    db.migrate()
    queue = JobService(db)

    async def scenario():
        entered, completed = asyncio.Event(), asyncio.Event()
        children = set()

        async def child(index):
            children.add(index)
            if len(children) == 3:
                entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                children.remove(index)

        async def blocked(payload, context):
            context.progress("images", 0.6)
            async with asyncio.TaskGroup() as group:
                for i in range(3):
                    group.create_task(child(i))

        async def next_handler(payload, context):
            completed.set()
            return {"next": True}

        queue.handlers.update(blocked=blocked, next=next_handler)
        first = queue.enqueue("blocked", "first", {"original": 1})
        second = queue.enqueue("next", "second", {})
        queue.start()
        await asyncio.wait_for(entered.wait(), 2)
        assert await queue.cancel_entity("first") == [first["id"]]
        assert not children
        await asyncio.wait_for(completed.wait(), 2)
        await queue.stop()
        stopped = queue.get(first["id"])
        assert stopped["status"] == "cancelled" and stopped["stage"] == "paused"
        assert stopped["progress"] == 0.6 and stopped["payload"] == {"original": 1}
        assert stopped["error_code"] == "JOB_CANCELLED"
        assert queue.get(second["id"])["status"] == "completed"
        with db.connect() as conn:
            assert not conn.execute(
                "SELECT 1 FROM processing_runs WHERE finished_at IS NULL"
            ).fetchone()
        queue.start()
        await asyncio.sleep(0.02)
        await queue.stop()
        assert queue.get(first["id"])["status"] == "cancelled"
        queue.handlers["blocked"] = next_handler
        assert queue.retry(first["id"])["payload"] == {"original": 1}
        assert await queue.run_one()
        assert queue.get(first["id"])["status"] == "completed"

    asyncio.run(scenario())


def test_cancel_before_handler_starts_or_after_deletion_does_not_kill_worker(tmp_path):
    db = Database(tmp_path / "app.db")
    db.migrate()
    queue = JobService(db)
    queue.enqueue("test", "first", {})

    async def scenario():
        calls = []

        async def handler(payload, context):
            calls.append(payload)

        queue.handlers["test"] = handler

        # Cancel the child synchronously at the exact registration boundary.
        class StopBeforeStart(dict):
            def __setitem__(self, identity, execution):
                super().__setitem__(identity, execution)
                with db.connect() as conn:
                    conn.execute("DELETE FROM jobs WHERE id=?", (identity,))
                execution.cancel()

        queue.executions = StopBeforeStart()
        assert await queue.run_one()
        assert not calls
        queue.executions = {}
        queue.enqueue("test", "second", {"next": 1})
        assert await queue.run_one()
        assert calls == [{"next": 1}]

    asyncio.run(scenario())
