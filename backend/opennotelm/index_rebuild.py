"""Durable, index-only rebuilds for the current global embedding model."""

import json
from uuid import uuid4

from .embedding_identity import index_signature
from .errors import AppError
from .model_service import now


class IndexRebuildService:
    def __init__(self, db, jobs, retrieval):
        self.db, self.jobs, self.retrieval = db, jobs, retrieval
        jobs.handlers["source_reindex"] = self.run

    def states(self, conn, signature):
        sources = conn.execute(
            "SELECT s.id,s.title FROM sources s WHERE s.parser_version IS NOT NULL "
            "AND EXISTS (SELECT 1 FROM notebook_sources ns WHERE ns.source_id=s.id) "
            "AND EXISTS (SELECT 1 FROM content_blocks b WHERE b.source_id=s.id "
            "AND length(trim(b.text))>0) ORDER BY s.created_at,s.id"
        ).fetchall()
        indexes = {
            row["source_id"]: dict(row)
            for row in conn.execute(
                "SELECT c.source_id,count(*) AS total,sum(e.config_hash=?) AS valid, "
                "min(e.created_at) AS indexed_at "
                "FROM chunks c LEFT JOIN embeddings e ON e.chunk_id=c.id GROUP BY c.source_id",
                (signature,),
            )
        }
        latest = {}
        for row in conn.execute(
            "SELECT * FROM jobs WHERE type='source_reindex' ORDER BY created_at,rowid"
        ):
            if json.loads(row["payload_json"]).get("config_hash") == signature:
                latest[row["entity_id"]] = dict(row)
        result = []
        for source in sources:
            job = latest.get(source["id"])
            index = indexes.get(source["id"], {})
            usable = bool(index.get("total") and index["total"] == index["valid"])
            active = job and job["status"] in ("queued", "running")
            failed = (
                job
                and job["status"] in ("failed", "cancelled")
                and (
                    not usable
                    or not job["finished_at"]
                    or index["indexed_at"] <= job["finished_at"]
                )
            )
            state = (
                job["status"]
                if active
                else "failed"
                if failed
                else "ready"
                if usable
                else "pending"
            )
            result.append(
                {
                    "source_id": source["id"],
                    "title": source["title"],
                    "state": state,
                    "usable": usable,
                    "progress": job["progress"] if active else 1 if state == "ready" else 0,
                    "error_code": job["error_code"] if failed else None,
                    "job_id": job["id"] if job else None,
                }
            )
        return result

    def status(self):
        model = self.retrieval.models.public_configs()["models"].get("embedding")
        if not model:
            return {"configured": False, "total": 0, "sources": [], "counts": {}}
        with self.db.connect() as conn:
            sources = self.states(conn, index_signature(model))
        return {
            "configured": True,
            "model_id": model["model_id"],
            "total": len(sources),
            "counts": {
                state: sum(s["state"] == state for s in sources)
                for state in ("ready", "queued", "running", "failed", "pending")
            },
            "sources": sources,
        }

    def enqueue_in_transaction(self, conn, signature, mode="missing", *, source_ids=None):
        queued = 0
        for source in self.states(conn, signature):
            if source_ids is not None and source["source_id"] not in source_ids:
                continue
            if mode == "failed" and source["state"] != "failed":
                continue
            if source["state"] in ("queued", "running"):
                continue
            if mode == "missing" and source["usable"]:
                continue
            payload = {
                "source_id": source["source_id"],
                "config_hash": signature,
                "force": mode in ("all", "failed"),
            }
            # Keep the durable unique active job. Queued work uses the latest model;
            # running work discards stale results, then continues with the new target.
            waiting = conn.execute(
                "SELECT id FROM jobs WHERE type='source_reindex' AND entity_id=? "
                "AND status IN ('queued','running') ORDER BY created_at,rowid LIMIT 1",
                (source["source_id"],),
            ).fetchone()
            if waiting:
                conn.execute(
                    "UPDATE jobs SET payload_json=? WHERE id=?",
                    (json.dumps(payload), waiting["id"]),
                )
            else:
                self.jobs.enqueue_in_transaction(
                    conn, "source_reindex", source["source_id"], payload
                )
            queued += 1
        return queued

    def rebuild(self, mode):
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT * FROM model_configs WHERE role='embedding'").fetchone()
            if not row:
                raise AppError("MODEL_NOT_CONFIGURED", "Configure the embedding model first.", 409)
            model = {**dict(row), "capabilities": json.loads(row["capabilities_json"])}
            states = self.states(conn, index_signature(model))
            if mode == "all" and any(source["state"] in ("queued", "running") for source in states):
                queued = 0
            else:
                if mode == "all" and states:
                    # A service may replace weights under the same name. Give this
                    # explicit recalculation a fresh identity so failed old vectors
                    # cannot be combined with queries from the changed model.
                    model["capabilities"]["index_signature"] = uuid4().hex
                    conn.execute(
                        "UPDATE model_configs SET capabilities_json=?,updated_at=? "
                        "WHERE role='embedding'",
                        (json.dumps(model["capabilities"]), now()),
                    )
                queued = self.enqueue_in_transaction(conn, index_signature(model), mode)
        return {"queued": queued, **self.status()}

    async def run(self, payload, context):
        while True:
            target = self.jobs.get(context.job["id"])["payload"]
            current = self.retrieval.embedding_config()[3]
            if current != target["config_hash"]:
                return {"superseded": True}
            try:
                return await self.retrieval.index(
                    target["source_id"], context, force=target.get("force", False)
                )
            except AppError:
                latest = self.jobs.get(context.job["id"])["payload"]
                if latest["config_hash"] == target["config_hash"]:
                    raise
