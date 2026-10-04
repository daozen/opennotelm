import json
from uuid import uuid4

from pydantic import Field

from .chunking import estimate_tokens
from .citations import GROUNDED_SYSTEM, INSUFFICIENT, CitationService
from .db import Database
from .errors import AppError
from .jobs import JobContext, JobService
from .languages import OutputLanguage, output_instruction
from .model_service import ModelService, now
from .notebooks import NotebookService
from .retrieval import RetrievalService, Scope
from .schemas import StrictModel


class ChatInput(StrictModel):
    question: str = Field(min_length=1, max_length=8000)
    scope: Scope = Field(default_factory=Scope)
    language: OutputLanguage | None = None


def fit_evidence(evidence: list[dict], budget: int) -> list[dict]:
    fitted, used = [], 0
    for packet in evidence:
        cost = estimate_tokens(packet["text"]) + 40
        if used + cost > budget:
            continue
        fitted.append(packet)
        used += cost
    return fitted


def bounded_text(text: str, budget: int) -> str:
    while text and estimate_tokens(text) > budget:
        text = text[: max(1, len(text) * 3 // 4)]
    return text


class ChatService:
    def __init__(
        self,
        db: Database,
        jobs: JobService,
        models: ModelService,
        retrieval: RetrievalService,
        citations: CitationService,
    ):
        self.db, self.jobs, self.models = db, jobs, models
        self.retrieval, self.citations = retrieval, citations
        jobs.handlers["chat_answer"] = self.answer

    def conversation(self, notebook_id: str) -> dict:
        NotebookService(self.db).get(notebook_id)
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT * FROM conversations WHERE notebook_id=? AND is_default=1", (notebook_id,)
            ).fetchone()
            if not row:
                conversation_id, timestamp = uuid4().hex, now()
                conn.execute(
                    "INSERT INTO conversations VALUES (?,?,?,1,?,?)",
                    (conversation_id, notebook_id, "Chat", timestamp, timestamp),
                )
                row = conn.execute(
                    "SELECT * FROM conversations WHERE id=?", (conversation_id,)
                ).fetchone()
        return dict(row)

    def messages(self, notebook_id: str) -> dict:
        conversation = self.conversation(notebook_id)
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM messages WHERE conversation_id=? ORDER BY created_at, rowid",
                (conversation["id"],),
            ).fetchall()
            messages = []
            for row in rows:
                message = dict(row)
                message["scope"] = json.loads(message.pop("scope_json"))
                message["metadata"] = json.loads(message.pop("metadata_json"))
                refs = conn.execute(
                    "SELECT evidence_id,id FROM citations WHERE owner_type='message' AND "
                    "owner_id=? ORDER BY rowid",
                    (row["id"],),
                ).fetchall()
                message["citations"] = {ref["evidence_id"]: ref["id"] for ref in refs}
                # Canonical legacy fallback stays in storage; expose a typed display hint.
                if message["role"] == "assistant" and message["content"] == INSUFFICIENT:
                    message["metadata"]["answer_status"] = "insufficient_evidence"
                job = conn.execute(
                    "SELECT id FROM jobs WHERE entity_id=? ORDER BY created_at DESC LIMIT 1",
                    (row["id"],),
                ).fetchone()
                message["job"] = self.jobs.get(job[0]) if job else None
                messages.append(message)
        return {"conversation": conversation, "messages": messages}

    def send(self, notebook_id: str, data: ChatInput) -> dict:
        question = data.question.strip()
        if not question:
            raise AppError("QUESTION_EMPTY", "Enter a question.")
        self.retrieval.resolve_scope(notebook_id, data.scope)
        conversation = self.conversation(notebook_id)
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            active = conn.execute(
                "SELECT 1 FROM jobs j JOIN messages m ON m.id=j.entity_id WHERE "
                "m.conversation_id=? AND j.status IN ('queued','running')",
                (conversation["id"],),
            ).fetchone()
            if active:
                raise AppError(
                    "CHAT_BUSY", "Wait for the current answer before sending another question.", 409
                )
            previous = conn.execute(
                "SELECT content FROM messages WHERE conversation_id=? AND role='user' "
                "ORDER BY created_at DESC,rowid DESC LIMIT 1",
                (conversation["id"],),
            ).fetchone()
            message_id = uuid4().hex
            # Freeze selected source IDs so later checkbox changes cannot widen a queued request.
            source_ids, _ = self.retrieval.resolve_scope(notebook_id, data.scope)
            scope = (
                data.scope.model_copy(update={"source_ids": source_ids})
                if data.scope.kind == "selected"
                else data.scope
            )
            conn.execute(
                "INSERT INTO messages VALUES (?,?, 'user',?,NULL,?,'{}',?)",
                (message_id, conversation["id"], question, scope.model_dump_json(), now()),
            )
            query = (
                f"{previous['content']}\n{question}"
                if previous and len(question) <= 80
                else question
            )
            job_id = self.jobs.enqueue_in_transaction(
                conn,
                "chat_answer",
                message_id,
                {
                    "notebook_id": notebook_id,
                    "message_id": message_id,
                    "conversation_id": conversation["id"],
                    "question": question,
                    "language": data.language,
                    "query": query,
                    "scope": scope.model_dump(),
                },
            )
        return self.jobs.get(job_id)

    async def answer(self, payload: dict, context: JobContext) -> dict:
        notebook_id, message_id = payload["notebook_id"], payload["message_id"]
        with self.db.connect() as conn:
            original = conn.execute("SELECT id FROM messages WHERE id=?", (message_id,)).fetchone()
            existing = conn.execute(
                "SELECT id,metadata_json FROM messages WHERE conversation_id=? AND "
                "role='assistant'",
                (payload["conversation_id"],),
            ).fetchall()
        if not original:
            raise AppError("CHAT_UNAVAILABLE", "The conversation has been removed.", 404)
        for row in existing:
            if json.loads(row["metadata_json"]).get("in_reply_to") == message_id:
                return {"message_id": row["id"], "skipped": True}
        context.progress("retrieving", 0.1)
        evidence, trace = await self.retrieval.search(
            notebook_id, Scope.model_validate(payload["scope"]), payload["query"], frozen=True
        )
        answer, model = INSUFFICIENT, None
        if evidence:
            config, key = self.models.configured("language")
            model = config.model_id
            budget = config.max_context_tokens
            evidence = fit_evidence(evidence, int(budget * 0.60))
            if not evidence:
                raise AppError(
                    "CONTEXT_BUDGET_EXCEEDED", "The evidence does not fit the model context budget."
                )
            current_question = payload["question"]
            if estimate_tokens(current_question) > budget * 0.10:
                raise AppError(
                    "QUESTION_TOO_LONG",
                    "Shorten the question or increase the context budget in Settings.",
                )
            context.progress("answering", 0.5)
            system = GROUNDED_SYSTEM
            if payload.get("language"):
                system += "\n" + output_instruction(payload["language"])
                system += (
                    "\nIf evidence is insufficient, retain the exact English control reply "
                    "specified above; the application localizes that system message."
                )
            output_reserve = max(256, min(4096, int(budget * 0.10)))
            while evidence:
                prompt = json.dumps(
                    {
                        "retrieval_question": bounded_text(payload["query"], int(budget * 0.10)),
                        "current_question": current_question,
                        "evidence": [{"id": item["id"], "text": item["text"]} for item in evidence],
                    },
                    ensure_ascii=False,
                )
                if (
                    estimate_tokens(system) + estimate_tokens(prompt) + 40
                    <= budget - output_reserve
                ):
                    break
                evidence.pop()
            if not evidence:
                raise AppError(
                    "CONTEXT_BUDGET_EXCEEDED", "Reduce the scope or increase the context budget."
                )
            answer = await self.models.gateway.text(
                config,
                key,
                [
                    {"role": "system", "content": system},
                    {"role": "user", "content": f"EVIDENCE_JSON\n{prompt}\nEND_EVIDENCE_JSON"},
                ],
                max_output_tokens=output_reserve,
            )
            context.progress("verifying_citations", 0.85)
            answer = await self.citations.validate(answer, evidence)
        assistant_id = uuid4().hex
        with self.db.connect() as conn:
            conn.execute(
                "INSERT INTO messages VALUES (?,?,'assistant',?,?,?,?,?)",
                (
                    assistant_id,
                    payload["conversation_id"],
                    answer,
                    model,
                    json.dumps(payload["scope"]),
                    json.dumps(
                        {
                            "in_reply_to": message_id,
                            "retrieval": trace,
                            "citation_verified": answer != INSUFFICIENT,
                            "language": payload.get("language"),
                        }
                    ),
                    now(),
                ),
            )
            self.citations.persist(conn, notebook_id, "message", assistant_id, answer, evidence)
            conn.execute(
                "UPDATE conversations SET updated_at=? WHERE id=?",
                (now(), payload["conversation_id"]),
            )
        return {"message_id": assistant_id}
