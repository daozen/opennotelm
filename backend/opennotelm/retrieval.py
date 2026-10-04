import heapq
import json
import math

from pydantic import Field

from .chunking import CHUNKER_VERSION, estimate_tokens, make_chunks
from .concurrency import bounded_map
from .db import Database
from .embedding_identity import index_signature
from .errors import AppError
from .jobs import JobContext
from .model_service import ModelService, now
from .passages import select_passages
from .schemas import StrictModel
from .source_service import SourceService


class Scope(StrictModel):
    kind: str = Field(default="selected", pattern="^(selected|source|node|nodes)$")
    source_ids: list[str] | None = Field(default=None, max_length=50)
    source_id: str | None = None
    node_id: str | None = None
    node_ids: list[str] | None = Field(default=None, min_length=1, max_length=10000)


class RetrievalService:
    def __init__(self, db: Database, models: ModelService, sources: SourceService):
        self.db, self.models, self.sources = db, models, sources

    def embedding_config(self):
        config, key, capabilities = self.models.configured_with_capabilities("embedding")
        dimensions = capabilities["dimensions"]
        model = {"model_id": config.model_id, "capabilities": capabilities}
        return config, key, dimensions, index_signature(model)

    async def index(self, source_id: str, context: JobContext, *, force=False) -> dict:
        try:
            config, key, dimensions, config_hash = self.embedding_config()
        except AppError as error:
            if error.code == "MODEL_NOT_CONFIGURED":
                return {"indexed": False, "needs_embedding_model": True}
            raise
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT count(*) AS total, sum(e.config_hash=?) AS valid FROM chunks c "
                "LEFT JOIN embeddings e ON e.chunk_id=c.id WHERE c.source_id=?",
                (config_hash, source_id),
            ).fetchone()
        if not force and row["total"] and row["total"] == row["valid"]:
            with self.db.connect() as conn:
                conn.execute(
                    "UPDATE sources SET "
                    "status='indexed',error_code=NULL,error_message=NULL WHERE id=?",
                    (source_id,),
                )
            return {"indexed": True, "skipped_index": True}
        blocks = self.sources.blocks(source_id)
        context.progress("chunking", 0.45)
        chunks = make_chunks(source_id, blocks)
        if not chunks:
            raise AppError("SOURCE_NO_TEXT", "There are no text blocks to index.")
        # New vectors are staged in memory; publish the replacement index atomically.
        completed = 0
        starts = list(range(0, len(chunks), 32))

        async def embed_batch(index, start):
            nonlocal completed
            batch = await self.models.gateway.embeddings(
                config, key, [c.text for c in chunks[start : start + 32]]
            )
            if any(len(v) != dimensions for v in batch):
                raise AppError(
                    "EMBEDDING_DIMENSIONS_CHANGED",
                    "Embedding dimensions changed. Retest the model in Settings.",
                )
            normalized = []
            for vector in batch:
                norm = math.hypot(*vector)
                if not math.isfinite(norm) or norm == 0:
                    raise AppError(
                        "EMBEDDING_OUTPUT_INVALID", "The endpoint returned invalid vectors."
                    )
                normalized.append([value / norm for value in vector])
            completed += 1
            context.progress("embedding", 0.5 + 0.45 * completed / len(starts))
            return normalized

        batches = await bounded_map(starts, embed_batch, 2)
        vectors = [vector for batch in batches for vector in batch]
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            model = conn.execute("SELECT * FROM model_configs WHERE role='embedding'").fetchone()
            current = {**dict(model), "capabilities": json.loads(model["capabilities_json"])}
            if index_signature(current) != config_hash:
                raise AppError(
                    "MODEL_CONFIG_CHANGED", "The embedding model changed. Retry indexing.", 409
                )
            conn.execute("DELETE FROM chunks WHERE source_id=?", (source_id,))
            for chunk, vector in zip(chunks, vectors, strict=True):
                conn.execute(
                    "INSERT INTO chunks(id,source_id,node_id,ordinal,text,token_count,"
                    "strategy_version) VALUES (?,?,?,?,?,?,?)",
                    (
                        chunk.id,
                        source_id,
                        chunk.node_id,
                        chunk.ordinal,
                        chunk.text,
                        estimate_tokens(chunk.text),
                        CHUNKER_VERSION,
                    ),
                )
                for ordinal, span in enumerate(chunk.spans):
                    conn.execute(
                        "INSERT INTO chunk_blocks VALUES (?,?,?,?,?)",
                        (chunk.id, span.block_id, ordinal, span.start, span.end),
                    )
                conn.execute(
                    "INSERT INTO embeddings VALUES (?,?,?,?,?,?)",
                    (chunk.id, config_hash, config.model_id, dimensions, json.dumps(vector), now()),
                )
            conn.execute(
                "UPDATE sources SET "
                "status='indexed',error_code=NULL,error_message=NULL,updated_at=? WHERE id=?",
                (now(), source_id),
            )
        return {"indexed": True, "chunk_count": len(chunks)}

    def resolve_scope(
        self, notebook_id: str, scope: Scope, *, frozen=False
    ) -> tuple[list[str], set[str] | None]:
        sources = self.sources.list(notebook_id)
        all_ids = {s["id"] for s in sources}
        selected = {s["id"] for s in sources if s["enabled"]}
        if scope.kind == "selected":
            requested = set(scope.source_ids) if scope.source_ids is not None else selected
            if not requested <= (all_ids if frozen else selected):
                raise AppError(
                    "SCOPE_INVALID", "Choose sources currently selected in this notebook."
                )
            return sorted(requested), None
        if scope.source_id not in all_ids:
            raise AppError("SCOPE_INVALID", "The requested source is not in this notebook.")
        if scope.kind == "source":
            return [scope.source_id], None
        nodes = self.sources.nodes(scope.source_id)
        requested = set(scope.node_ids or []) if scope.kind == "nodes" else {scope.node_id}
        if not requested or not requested <= {n["id"] for n in nodes}:
            raise AppError("SCOPE_INVALID", "The requested section is not in this source.")
        children = {}
        for node in nodes:
            children.setdefault(node["parent_id"], []).append(node["id"])
        descendants, pending = set(), list(requested)
        while pending:
            identity = pending.pop()
            if identity not in descendants:
                descendants.add(identity)
                pending.extend(children.get(identity, []))
        for node in nodes:
            if node["id"] in descendants:
                descendants.update(node["metadata"].get("section_block_ids", []))
        return [scope.source_id], descendants

    def scope_blocks(self, notebook_id: str, scope: Scope, *, frozen=False) -> list[dict]:
        source_ids, node_ids = self.resolve_scope(notebook_id, scope, frozen=frozen)
        return [
            block
            for source_id in source_ids
            for block in self.sources.blocks(source_id)
            if node_ids is None or block["node_id"] in node_ids or block["id"] in node_ids
        ]

    async def search(
        self, notebook_id: str, scope: Scope, query: str, top_k=12, *, frozen=False
    ) -> tuple[list[dict], dict]:
        source_ids, node_ids = self.resolve_scope(notebook_id, scope, frozen=frozen)
        trace = {
            "query": query,
            "scope": scope.model_dump(),
            "chunk_ids": [],
            "scores": [],
            "chunker_version": CHUNKER_VERSION,
        }
        if not source_ids:
            return [], trace
        config, key, dimensions, config_hash = self.embedding_config()
        trace["embedding_model"] = config.model_id
        marks = ",".join("?" for _ in source_ids)
        with self.db.connect() as conn:
            for source_id in source_ids:
                counts = conn.execute(
                    "SELECT count(*) AS total, sum(e.config_hash=?) AS valid FROM chunks c "
                    "LEFT JOIN embeddings e ON e.chunk_id=c.id WHERE c.source_id=?",
                    (config_hash, source_id),
                ).fetchone()
                if not counts["total"] or counts["total"] != counts["valid"]:
                    raise AppError(
                        "SOURCE_INDEX_REQUIRED",
                        "Selected sources need indexing. "
                        "Check progress or retry in model settings.",
                        409,
                    )
        vector = (await self.models.gateway.embeddings(config, key, [query]))[0]
        norm = math.hypot(*vector)
        if len(vector) != dimensions or not math.isfinite(norm) or norm == 0:
            raise AppError(
                "EMBEDDING_DIMENSIONS_CHANGED",
                "Retest the embedding model and rebuild the source index.",
            )
        vector = [v / norm for v in vector]
        heap = []
        with self.db.connect() as conn:
            permitted_chunks = None
            if node_ids is not None:
                permitted_chunks = {
                    row["chunk_id"]
                    for row in conn.execute(
                        "SELECT cb.chunk_id,b.id,b.node_id FROM chunk_blocks cb "
                        "JOIN content_blocks b ON b.id=cb.block_id "
                        f"WHERE b.source_id IN ({marks})",
                        source_ids,
                    )
                    if row["node_id"] in node_ids or row["id"] in node_ids
                }
            rows = conn.execute(
                f"SELECT c.*,e.vector_json FROM chunks c JOIN embeddings e ON e.chunk_id=c.id "
                f"WHERE c.source_id IN ({marks}) AND e.config_hash=?",
                (*source_ids, config_hash),
            )
            for row in rows:
                if permitted_chunks is not None and row["id"] not in permitted_chunks:
                    continue
                stored = json.loads(row["vector_json"])
                score = math.fsum(a * b for a, b in zip(vector, stored, strict=True))
                candidate = (score, row["id"], dict(row))
                if len(heap) < top_k:
                    heapq.heappush(heap, candidate)
                elif candidate[:2] > heap[0][:2]:
                    heapq.heapreplace(heap, candidate)
            ranked = sorted(heap, reverse=True)
            packets = []
            for score, chunk_id, _chunk in ranked:
                spans = [
                    dict(row)
                    for row in conn.execute(
                        "SELECT cb.*,b.source_id,b.node_id,b.text FROM chunk_blocks cb "
                        "JOIN content_blocks b "
                        "ON b.id=cb.block_id WHERE cb.chunk_id=? ORDER BY cb.ordinal",
                        (chunk_id,),
                    )
                    if node_ids is None or row["node_id"] in node_ids or row["block_id"] in node_ids
                ]
                packets.append({"score": score, "chunk_id": chunk_id, "spans": spans})
        trace["chunk_ids"], trace["scores"] = (
            [c[1] for c in ranked],
            [round(c[0], 4) for c in ranked],
        )
        # Treat readable paragraphs, rather than PDF drawing fragments, as
        # provider-facing evidence. Existing indexes still locate immutable hits.
        by_source: dict[str, list[dict]] = {}
        for packet in packets:
            for span in packet["spans"]:
                by_source.setdefault(span["source_id"], []).append(span)
        paragraphs = [
            passage
            for source_id, hits in by_source.items()
            for passage in self.sources.passages(source_id, hits, node_ids)
        ]
        selected = select_passages(
            paragraphs, [hit for packet in packets for hit in packet["spans"]]
        )
        evidence = [{"id": f"E{index + 1}", **passage} for index, passage in enumerate(selected)]
        trace["evidence_version"] = "paragraph-v1"
        return evidence, trace
