import json
import re
import time
from typing import Literal
from uuid import uuid4

from pydantic import Field

from .citations import CITATION_PATTERN
from .errors import AppError
from .languages import OutputLanguage
from .model_service import now
from .retrieval import Scope
from .schemas import StrictModel


class TransformationInput(StrictModel):
    kind: Literal["summary", "outline"]
    scope: Scope = Field(default_factory=Scope)
    language: OutputLanguage | None = None


class TransformationService:
    def __init__(self, db, jobs, knowledge):
        self.db, self.jobs, self.knowledge = db, jobs, knowledge
        jobs.handlers["transform_source"] = self.generate
        self.cleanup()

    def cleanup(self):
        with self.db.connect() as conn:
            conn.execute(
                "UPDATE transformations SET discarded=1 WHERE expires_at<=?", (int(time.time()),)
            )
            rows = conn.execute(
                "SELECT t.id,t.job_id FROM transformations t LEFT JOIN jobs j ON j.id=t.job_id "
                "WHERE t.discarded=1 AND (j.status NOT IN ('queued','running') OR j.id IS NULL)"
            ).fetchall()
            for row in rows:
                conn.execute("DELETE FROM transformations WHERE id=?", (row["id"],))
                conn.execute("DELETE FROM jobs WHERE id=?", (row["job_id"],))

    def create(self, notebook_id, data):
        self.cleanup()
        scope = self.knowledge.freeze(notebook_id, data.scope)
        self.knowledge.models.configured("language")
        identity = uuid4().hex
        with self.db.connect() as conn:
            job_id = self.jobs.enqueue_in_transaction(
                conn,
                "transform_source",
                identity,
                {
                    "transformation_id": identity,
                    "notebook_id": notebook_id,
                    "kind": data.kind,
                    "language": data.language,
                    "scope": scope.model_dump(),
                },
            )
            conn.execute(
                "INSERT INTO transformations(id,notebook_id,kind,job_id,expires_at) "
                "VALUES (?,?,?,?,?)",
                (identity, notebook_id, data.kind, job_id, int(time.time()) + 86400),
            )
        return self.get(identity)

    def get(self, identity):
        self.cleanup()
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT * FROM transformations WHERE id=? AND discarded=0", (identity,)
            ).fetchone()
        if not row:
            raise AppError(
                "TRANSFORMATION_UNAVAILABLE",
                "This temporary result has expired or was dismissed.",
                404,
            )
        value = dict(row)
        value["evidence"] = json.loads(value.pop("evidence_json"))
        value["generation_metadata"] = json.loads(value.pop("metadata_json"))
        value["citations"] = {
            marker: f"preview:{identity}:{marker}"
            for marker in dict.fromkeys(CITATION_PATTERN.findall(value["content_markdown"]))
        }
        value["title"] = "资料摘要" if value["kind"] == "summary" else "资料提纲"
        value["revision"] = 0
        value["job"] = self.jobs.get(value["job_id"])
        return value

    async def generate(self, payload, context):
        try:
            result = self.get(payload["transformation_id"])
        except AppError as error:
            if error.code == "TRANSFORMATION_UNAVAILABLE":
                return {"discarded": True}
            raise
        if result["content_markdown"]:
            return {"transformation_id": result["id"], "skipped": True}
        blocks = self.knowledge.retrieval.scope_blocks(
            payload["notebook_id"], Scope.model_validate(payload["scope"]), frozen=True
        )
        content, evidence, metadata = await self.knowledge.synthesis.run(
            blocks, context, purpose=payload["kind"], output_language=payload.get("language")
        )
        with self.db.connect() as conn:
            published = conn.execute(
                "UPDATE transformations SET content_markdown=?,evidence_json=?,metadata_json=? "
                "WHERE id=? AND discarded=0 AND expires_at>?",
                (
                    content,
                    json.dumps(evidence),
                    json.dumps(metadata),
                    result["id"],
                    int(time.time()),
                ),
            ).rowcount
            if not published:
                conn.execute(
                    "DELETE FROM synthesis_checkpoints WHERE job_id=?", (context.job["id"],)
                )
        return {"transformation_id": result["id"], "discarded": not bool(published)}

    def discard(self, identity):
        with self.db.connect() as conn:
            conn.execute(
                "UPDATE transformations SET discarded=1,content_markdown='',"
                "evidence_json='[]',metadata_json='{}' WHERE id=?",
                (identity,),
            )
        self.cleanup()

    def citation(self, citation_id):
        parts = citation_id.split(":", 2)
        if len(parts) != 3:
            raise AppError("CITATION_NOT_FOUND", "This citation is unavailable.", 404)
        value = self.get(parts[1])
        packet = next((item for item in value["evidence"] if item["id"] == parts[2]), None)
        if not packet or parts[2] not in value["citations"]:
            raise AppError("CITATION_NOT_FOUND", "This citation is unavailable.", 404)
        spans = self.knowledge.citations.preview_spans(packet["spans"])
        return {"id": citation_id, "spans": spans, "available": all(s["available"] for s in spans)}

    def save(self, identity):
        value = self.get(identity)
        if not value["content_markdown"]:
            raise AppError(
                "TRANSFORMATION_NOT_READY", "Wait for the temporary result to finish.", 409
            )
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT * FROM transformations WHERE id=? AND discarded=0 AND expires_at>?",
                (identity, int(time.time())),
            ).fetchone()
            if not row:
                raise AppError(
                    "TRANSFORMATION_UNAVAILABLE", "This result is no longer available.", 404
                )
            page_id = row["saved_page_id"]
            if not page_id:
                page_id, timestamp = uuid4().hex, now()
                title = (
                    re.sub(r"^#+\s*", "", value["content_markdown"].splitlines()[0]).strip()[:200]
                    or value["title"]
                )
                conn.execute(
                    "INSERT INTO knowledge_pages VALUES (?,?,?,?,?,?,1,?,?)",
                    (
                        page_id,
                        value["notebook_id"],
                        title,
                        page_id[:12],
                        value["content_markdown"],
                        json.dumps(
                            {
                                **value["generation_metadata"],
                                "saved_from_transformation": value["kind"],
                            }
                        ),
                        timestamp,
                        timestamp,
                    ),
                )
                self.knowledge.citations.persist(
                    conn,
                    value["notebook_id"],
                    "knowledge",
                    page_id,
                    value["content_markdown"],
                    value["evidence"],
                )
                conn.execute(
                    "UPDATE transformations SET saved_page_id=? WHERE id=?", (page_id, identity)
                )
                conn.execute(
                    "UPDATE notebooks SET updated_at=? WHERE id=?",
                    (timestamp, value["notebook_id"]),
                )
        return self.knowledge.get(page_id)
