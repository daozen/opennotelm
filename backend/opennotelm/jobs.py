import asyncio
import json
import time
from collections.abc import Awaitable, Callable
from uuid import uuid4
from weakref import WeakValueDictionary

from .db import Database
from .errors import AppError
from .job_events import record_job
from .model_service import now

JobHandler = Callable[[dict, "JobContext"], Awaitable[dict | None]]


class JobContext:
    def __init__(self, service: "JobService", job: dict):
        self.service, self.job = service, job

    def progress(self, stage: str, progress: float) -> None:
        with self.service.db.connect() as conn:
            conn.execute(
                "UPDATE jobs SET stage=?, progress=? WHERE id=? AND status='running'",
                (stage, min(1.0, max(0.0, progress)), self.job["id"]),
            )

    def substage(self, stage: str, start: float, end: float):
        return ProgressContext(self, stage, start, end)


class ProgressContext:
    """Map a nested pipeline's progress into its parent's range."""

    def __init__(self, parent, stage, start, end):
        self.parent, self.stage, self.start, self.end = parent, stage, start, end
        self.job = parent.job

    def progress(self, stage, progress):
        self.parent.progress(
            self.stage, self.start + (self.end - self.start) * min(1, max(0, progress))
        )


class JobService:
    def __init__(self, db: Database, telemetry=None, *, concurrency=None):
        self.db = db
        self.telemetry = telemetry
        self.handlers: dict[str, JobHandler] = {}
        self.task: asyncio.Task | None = None
        self.executions: dict[str, asyncio.Task] = {}
        self.entity_locks = WeakValueDictionary()
        self.concurrency = concurrency or (lambda: 1)
        self.last_group = None

    def entity_lock(self, entity_id: str) -> asyncio.Lock:
        lock = self.entity_locks.get(entity_id)
        if lock is None:
            lock = asyncio.Lock()
            self.entity_locks[entity_id] = lock
        return lock

    async def cancel_entity(self, entity_id: str) -> list[str]:
        """Persist cancellation before interrupting and joining all in-flight work."""
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            ids = [
                row[0]
                for row in conn.execute(
                    "SELECT id FROM jobs WHERE entity_id=? AND status IN ('queued','running')",
                    (entity_id,),
                )
            ]
            conn.execute(
                "UPDATE jobs SET status='cancelled',stage='paused',error_code='JOB_CANCELLED',"
                "error_message='Generation stopped. Saved progress can be resumed.',"
                "finished_at=? WHERE entity_id=? AND status IN ('queued','running')",
                (now(), entity_id),
            )
            if ids:
                conn.execute(
                    "UPDATE decks SET status='paused',updated_at=? WHERE id=?",
                    (now(), entity_id),
                )
        tasks = [self.executions[identity] for identity in ids if identity in self.executions]
        for task in tasks:
            if not task.cancelling():
                task.cancel()
        if tasks:
            joined = asyncio.gather(*tasks, return_exceptions=True)
            try:
                await asyncio.shield(joined)
            except asyncio.CancelledError:
                # Do not interrupt thread/file cleanup a second time on request disconnect.
                await joined
                raise
        return ids

    def get(self, job_id: str) -> dict:
        with self.db.connect() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if not row:
            raise AppError("JOB_NOT_FOUND", "This task no longer exists.", 404)
        job = dict(row)
        job["payload"] = json.loads(job.pop("payload_json"))
        job["result"] = json.loads(job.pop("result_json") or "null")
        return job

    def enqueue(self, kind: str, entity_id: str, payload: dict) -> dict:
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            job_id = self.enqueue_in_transaction(conn, kind, entity_id, payload)
        return self.get(job_id)

    def enqueue_in_transaction(self, conn, kind: str, entity_id: str, payload: dict) -> str:
        existing = conn.execute(
            "SELECT id FROM jobs WHERE type=? AND entity_id=? AND status IN ('queued','running')",
            (kind, entity_id),
        ).fetchone()
        job_id = existing[0] if existing else uuid4().hex
        if not existing:
            notebook_id = payload.get("notebook_id")
            if kind in ("deck_generate", "deck_export", "slide_revision"):
                deck = conn.execute(
                    "SELECT notebook_id FROM decks WHERE id=?", (entity_id,)
                ).fetchone()
                notebook_id = deck[0] if deck else None
            conn.execute(
                "INSERT INTO jobs(id,type,entity_id,status,payload_json,created_at,"
                "notebook_id,source_id) "
                "VALUES (?,?,?,'queued',?,?,?,?)",
                (
                    job_id,
                    kind,
                    entity_id,
                    json.dumps(payload),
                    now(),
                    notebook_id,
                    entity_id
                    if kind in ("source_ingest", "source_web_images", "source_reindex")
                    else None,
                ),
            )
        return job_id

    def retry(self, job_id: str) -> dict:
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            job = self.get(job_id)
            if job["status"] not in ("failed", "cancelled"):
                raise AppError(
                    "JOB_NOT_RETRYABLE", "Only failed or cancelled tasks can be retried.", 409
                )
            active = conn.execute(
                "SELECT id,type FROM jobs WHERE entity_id=? AND status IN ('queued','running')",
                (job["entity_id"],),
            ).fetchone()
            if active:
                if active["type"] == job["type"]:
                    return self.get(active["id"])
                raise AppError("ENTITY_BUSY", "Wait for the current task before retrying.", 409)
            conn.execute(
                "UPDATE jobs SET status='queued', error_code=NULL, error_message=NULL, "
                "stage='resuming',finished_at=NULL, retry_count=retry_count+1 WHERE id=?",
                (job_id,),
            )
        return self.get(job_id)

    def start(self) -> None:
        if self.task and not self.task.done():
            return
        with self.db.connect() as conn:
            # Single-instance architecture: interrupted work is resumable on restart.
            conn.execute(
                "UPDATE processing_runs SET finished_at=?,error_code='JOB_INTERRUPTED' "
                "WHERE finished_at IS NULL",
                (now(),),
            )
            conn.execute("UPDATE jobs SET status='queued', stage='resuming' WHERE status='running'")
        self.task = asyncio.create_task(self.run())

    async def stop(self) -> None:
        if self.task:
            if not self.task.cancelling():
                self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass

    def claim(self) -> dict | None:
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            active = list(conn.execute("SELECT * FROM jobs WHERE status='running'"))
            # Explicit cancellation changes DB status before file/native cleanup is joined.
            for identity in self.executions:
                if not any(job["id"] == identity for job in active):
                    reserved = conn.execute("SELECT * FROM jobs WHERE id=?", (identity,)).fetchone()
                    if reserved:
                        active.append(reserved)
            queued = conn.execute(
                "SELECT * FROM jobs WHERE status='queued' ORDER BY created_at,rowid"
            ).fetchall()
            reservations = [(job, self.source_access(conn, job)) for job in active]
            candidates = []
            for candidate in queued:
                access = self.source_access(conn, candidate)
                if any(
                    candidate["entity_id"] == other["entity_id"]
                    or access[0] & (reserved[0] | reserved[1])
                    or access[1] & reserved[0]
                    for other, reserved in reservations
                ):
                    # Prevent an older source writer from starving behind new readers.
                    reservations.append((candidate, access))
                else:
                    candidates.append(candidate)
                    reservations.append((candidate, access))
            # Alternate task families when possible, preserving resource FIFO.
            # A large Deck batch must not monopolize every newly available slot.
            groups = ("source", "deck", "podcast", "mindmap", "interactive")
            if candidates and self.last_group is not None:
                offset = groups.index(self.last_group) + 1
                row = min(
                    candidates,
                    key=lambda job: (groups.index(self.group(job)) - offset) % len(groups),
                )
            else:
                row = candidates[0] if candidates else None
            if row:
                self.last_group = self.group(row)
                conn.execute(
                    "UPDATE jobs SET status='running', started_at=? WHERE id=?", (now(), row["id"])
                )
        return self.get(row["id"]) if row else None

    @staticmethod
    def group(job):
        if job["type"].startswith("source_"):
            return "source"
        if job["type"] in ("deck_generate", "deck_export", "slide_revision"):
            return "deck"
        if job["type"] == "podcast_generate":
            return "podcast"
        if job["type"] == "mindmap_generate":
            return "mindmap"
        return "interactive"

    @staticmethod
    def source_access(conn, job):
        if job["type"] in ("source_ingest", "source_web_images", "source_reindex"):
            return {job["entity_id"]}, set()
        payload = json.loads(job["payload_json"])
        scope = payload.get("scope")
        snapshot_sources = set()
        if job["type"] in ("deck_generate", "deck_export", "slide_revision"):
            deck = conn.execute(
                "SELECT source_scope_json,knowledge_snapshot_json FROM decks WHERE id=?",
                (job["entity_id"],),
            ).fetchone()
            scope = json.loads(deck[0]) if deck else None
            if deck:
                snapshot = json.loads(deck[1] or "null") or {}
                for identity in (snapshot.get("citations") or {}).values():
                    snapshot_sources.update(
                        row[0]
                        for row in conn.execute(
                            "SELECT source_id FROM citation_spans WHERE citation_id=?", (identity,)
                        )
                    )
        if job["type"] in ("podcast_generate", "mindmap_generate"):
            table = "podcasts" if job["type"] == "podcast_generate" else "mindmaps"
            episode = conn.execute(
                f"SELECT source_scope_json,knowledge_snapshot_json FROM {table} WHERE id=?",
                (job["entity_id"],),
            ).fetchone()
            scope = json.loads(episode[0]) if episode else None
            snapshot = json.loads(episode[1] or "null") if episode else None
            for citation in (snapshot or {}).get("citations", {}).values():
                snapshot_sources.update(
                    r[0]
                    for r in conn.execute(
                        "SELECT source_id FROM citation_spans WHERE citation_id=?", (citation,)
                    )
                )
        if scope:
            sources = snapshot_sources | set(scope.get("source_ids") or [])
            if scope.get("source_id"):
                sources.add(scope["source_id"])
            if sources:
                return set(), sources
        # Older jobs and Knowledge snapshots may not have explicit frozen IDs.
        return set(), snapshot_sources | {
            row[0]
            for row in conn.execute(
                "SELECT source_id FROM notebook_sources WHERE notebook_id=?", (job["notebook_id"],)
            )
        }

    async def run_one(self) -> bool:
        job = self.claim()
        if not job:
            return False
        execution = asyncio.create_task(self.execute(job))
        self.executions[job["id"]] = execution
        try:
            await execution
        except asyncio.CancelledError:
            # A task can be stopped before its coroutine starts. Keep the worker alive.
            with self.db.connect() as conn:
                row = conn.execute("SELECT status FROM jobs WHERE id=?", (job["id"],)).fetchone()
            if asyncio.current_task().cancelling() or (row and row[0] != "cancelled"):
                raise
        finally:
            self.executions.pop(job["id"], None)
        if asyncio.current_task().cancelling():
            raise asyncio.CancelledError
        return True

    async def execute(self, job: dict) -> None:
        from .generation_attempts import JOB_DIAGNOSTICS

        diagnostic_token = JOB_DIAGNOSTICS.set((self.db, job["id"]))
        context = JobContext(self, job)
        run_id = uuid4().hex
        with self.db.connect() as conn:
            conn.execute(
                "INSERT INTO processing_runs(id,entity_id,job_id,stage,started_at,version) "
                "VALUES (?,?,?,?,?,'v1')",
                (run_id, job["entity_id"], job["id"], job["type"], now()),
            )
        error, result = None, None
        started = time.monotonic()
        try:
            record_job(self, job, "started")
            handler = self.handlers.get(job["type"])
            if not handler:
                raise AppError(
                    "JOB_HANDLER_UNAVAILABLE", "This task is unsupported by this app version."
                )
            result = await handler(job["payload"], context)
            with self.db.connect() as conn:
                conn.execute(
                    "UPDATE jobs SET status='completed', stage='completed', progress=1, "
                    "result_json=?, finished_at=? WHERE id=? AND status='running'",
                    (json.dumps(result), now(), job["id"]),
                )
        except asyncio.CancelledError:
            with self.db.connect() as conn:
                row = conn.execute("SELECT status FROM jobs WHERE id=?", (job["id"],)).fetchone()
                explicitly_cancelled = not row or row[0] == "cancelled"
                if not explicitly_cancelled:
                    conn.execute(
                        "UPDATE jobs SET status='queued', stage='resuming' WHERE id=?",
                        (job["id"],),
                    )
            error = AppError(
                "JOB_CANCELLED" if explicitly_cancelled else "JOB_INTERRUPTED",
                "Generation stopped."
                if explicitly_cancelled
                else "The task will resume on restart.",
            )
            if not explicitly_cancelled:
                raise
        except Exception as exc:
            error = (
                exc
                if isinstance(exc, AppError)
                else AppError(
                    "JOB_PROCESSING_FAILED", "The task failed. Retry or export diagnostics."
                )
            )
            with self.db.connect() as conn:
                conn.execute(
                    "UPDATE jobs SET status='failed', error_code=?, error_message=?, finished_at=? "
                    "WHERE id=? AND status='running'",
                    (error.code, error.message, now(), job["id"]),
                )
        finally:
            JOB_DIAGNOSTICS.reset(diagnostic_token)
            with self.db.connect() as conn:
                conn.execute(
                    "UPDATE processing_runs SET finished_at=?,error_code=? WHERE id=?",
                    (now(), error.code if error else None, run_id),
                )
            record_job(
                self,
                job,
                "cancelled"
                if error and error.code == "JOB_CANCELLED"
                else "failed"
                if error
                else "completed",
                int((time.monotonic() - started) * 1000),
                error,
                result,
            )

    async def run(self) -> None:
        try:
            while True:
                for identity, task in list(self.executions.items()):
                    if task.done():
                        self.executions.pop(identity)
                        if not task.cancelled():
                            task.result()
                while len(self.executions) < self.concurrency():
                    job = self.claim()
                    if job is None:
                        break
                    self.executions[job["id"]] = asyncio.create_task(self.execute(job))
                if self.executions:
                    await asyncio.wait(
                        self.executions.values(), timeout=0.25, return_when=asyncio.FIRST_COMPLETED
                    )
                else:
                    await asyncio.sleep(0.25)
        finally:
            identities = list(self.executions)
            tasks = list(self.executions.values())
            for task in tasks:
                if not task.cancelling():
                    task.cancel()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            # A claimed coroutine may be cancelled before its first instruction.
            with self.db.connect() as conn:
                for identity in identities:
                    conn.execute(
                        "UPDATE jobs SET status='queued',stage='resuming' "
                        "WHERE id=? AND status='running'",
                        (identity,),
                    )
            self.executions.clear()
