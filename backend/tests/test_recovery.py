import asyncio
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient
from opennotelm.errors import AppError
from opennotelm.instance import instance_lock
from opennotelm.main import create_app


def test_second_instance_cannot_migrate_or_recover_owned_jobs(client, settings, provider):
    queue = client.app.state.jobs
    client.portal.call(queue.stop)
    job = queue.enqueue("test", "pending", {})
    queue.claim()
    with pytest.raises(AppError, match="INSTANCE_ALREADY_RUNNING"):
        with TestClient(create_app(settings, transport=provider[0])):
            pytest.fail("The second instance must not start")
    assert queue.get(job["id"])["status"] == "running"
    client.__exit__(None, None, None)
    with TestClient(create_app(settings, transport=provider[0])) as restarted:
        from test_sources import wait_for_job

        recovered = wait_for_job(restarted, job["id"])
        assert recovered["error_code"] == "JOB_HANDLER_UNAVAILABLE"


def test_os_releases_instance_lock_after_abrupt_process_exit(tmp_path):
    program = (
        "import sys,time; from pathlib import Path; "
        "from opennotelm.instance import instance_lock; "
        "owner=instance_lock(Path(sys.argv[1])); owner.__enter__(); "
        "print('locked', flush=True); time.sleep(20)"
    )
    process = subprocess.Popen(
        [sys.executable, "-c", program, str(tmp_path)], stdout=subprocess.PIPE, text=True
    )
    try:
        assert process.stdout.readline().strip() == "locked"
        with pytest.raises(AppError, match="INSTANCE_ALREADY_RUNNING"):
            with instance_lock(tmp_path):
                pytest.fail("Another process owns the directory")
    finally:
        process.kill()
        process.wait(timeout=5)
    with instance_lock(tmp_path):
        assert (tmp_path / "instance.lock").is_file()


def test_graceful_shutdown_records_interruption_and_resumes_once(tmp_path):
    from opennotelm.db import Database
    from opennotelm.jobs import JobService

    db = Database(tmp_path / "app.db")
    db.migrate()
    queue = JobService(db)
    job = queue.enqueue("test", "entity", {})
    calls = []

    async def scenario():
        begun = asyncio.Event()

        async def interrupted(payload, context):
            calls.append("interrupted")
            context.progress("saved_stage", 0.4)
            begun.set()
            await asyncio.Event().wait()

        queue.handlers["test"] = interrupted
        queue.start()
        task = queue.task
        queue.start()
        assert queue.task is task
        await asyncio.wait_for(begun.wait(), 2)
        await queue.stop()
        assert queue.get(job["id"])["status"] == "queued"
        restarted = JobService(db)
        finished = asyncio.Event()

        async def resumed(payload, context):
            calls.append("resumed")
            finished.set()
            return {"saved": True}

        restarted.handlers["test"] = resumed
        restarted.start()
        await asyncio.wait_for(finished.wait(), 2)
        await restarted.stop()

    asyncio.run(scenario())
    assert calls == ["interrupted", "resumed"]
    assert queue.get(job["id"])["status"] == "completed"
    with db.connect() as conn:
        traces = conn.execute(
            "SELECT error_code,finished_at FROM processing_runs ORDER BY rowid"
        ).fetchall()
    assert [row["error_code"] for row in traces] == ["JOB_INTERRUPTED", None]
    assert all(row["finished_at"] for row in traces)
