import asyncio
import json
import math
import re
from uuid import uuid4

from . import deck_sources
from .citations import CITATION_PATTERN
from .concurrency import CONTENT_CONCURRENCY, bounded_map, joined_thread
from .content_generation_settings import ContentGenerationSettingsService
from .deck_art import DeckArtService
from .deck_content import (
    CONTENT_POLICY,
    CONTENT_POLICY_VERSION,
    GROUNDING,
    check_content_basis,
    check_source_content,
)
from .deck_context import WORK_CONTEXT_POLICY, WorkContextService, page_context
from .deck_schemas import (
    DeckBrief,
    DeckInput,
    DeckPlan,
    DeckPreferences,
    DeckStyleManifest,
    SlideSpec,
)
from .deck_style import STYLE_SYSTEM, STYLE_VERSION, AdaptiveDeckStyle, style_data, validate_style
from .deck_style import enabled as adaptive_style
from .deck_validation import diagnose_page
from .errors import AppError
from .generated_pages import GENERATION_VERSION as PAGE_GENERATION_VERSION
from .generated_pages import uses_generated_pages
from .image_generation_settings import ImageGenerationSettingsService
from .model_service import now
from .notebooks import NotebookService
from .output_repair import EvidenceValidationError, FieldValidationError
from .page_design import GENERATION_VERSION
from .render_schemas import content_fragments
from .request_limits import SharedStageBudget
from .retrieval import Scope
from .source_visuals import MAX_IMAGES, VISUAL_PLACEHOLDER, bind_visuals, visual_manifest
from .structured import structured_completion

MAX_BATCH_DECKS = 100


class DeckService:
    def __init__(self, db, jobs, models, knowledge, citations, settings):
        self.db, self.jobs, self.models = db, jobs, models
        self.knowledge, self.citations = knowledge, citations
        self.settings = settings
        self.render_budget = SharedStageBudget()
        self.image_generation_settings = ImageGenerationSettingsService(db, settings)
        self.content_generation_settings = ContentGenerationSettingsService(db, settings)
        self.composition = None
        self.assets = None
        self.exports = None
        self.revisions = None
        self.art = DeckArtService(db, models)
        self.work_context = WorkContextService(knowledge.retrieval.sources, knowledge.synthesis)
        jobs.handlers["deck_generate"] = self.generate

    def record(self, deck_id):
        with self.db.connect() as conn:
            row = conn.execute("SELECT * FROM decks WHERE id=?", (deck_id,)).fetchone()
        if not row:
            raise AppError("DECK_NOT_FOUND", "This deck no longer exists.", 404)
        deck = dict(row)
        for name in (
            "source_scope",
            "brief",
            "plan",
            "style",
            "understanding",
            "knowledge_snapshot",
            "generation_metadata",
            "source_manifest",
        ):
            deck[name] = json.loads(deck.pop(name + "_json") or "null")
        return deck

    def get(self, deck_id):
        deck = self.record(deck_id)
        deck["render_mode"] = "generated_page" if uses_generated_pages(deck) else "native"
        deck["art_direction"] = (deck.get("generation_metadata") or {}).get("art_direction")
        deck.pop("understanding")
        deck.pop("knowledge_snapshot")
        deck.pop("source_manifest")
        deck.pop("export_title")
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM slides WHERE deck_id=? ORDER BY ordinal", (deck_id,)
            ).fetchall()
            slides = []
            for row in rows:
                slide = dict(row)
                slide["plan"] = json.loads(slide.pop("plan_json"))
                slide["spec"] = json.loads(slide.pop("spec_json") or "null")
                slide["assets"] = self.assets.list(slide["id"]) if self.assets else []
                slide["render_current"] = row["current_render_revision"] == row["revision"]
                slide["render"] = (
                    self.composition.public(slide["current_render_id"])
                    if (self.composition and slide["current_render_id"])
                    else None
                )
                current_markers = (
                    SlideSpec.model_validate(slide["spec"]).citation_ids() if slide["spec"] else []
                )
                slide["citations"] = {
                    r["evidence_id"]: r["id"]
                    for r in conn.execute(
                        "SELECT evidence_id,id FROM citations WHERE owner_type='slide' "
                        "AND owner_id=? ORDER BY rowid",
                        (row["id"],),
                    )
                    if r["evidence_id"] in current_markers
                }
                slides.append(slide)
            job = conn.execute(
                "SELECT id FROM jobs WHERE entity_id=? ORDER BY status IN "
                "('queued','running') DESC,coalesce(finished_at,started_at,created_at) DESC,"
                "rowid DESC LIMIT 1",
                (deck_id,),
            ).fetchone()
        deck["slides"] = slides
        deck["slide_count"] = len(slides) if deck["plan"] else deck["target_slide_count"]
        deck["job"] = self.jobs.get(job["id"]) if job else None
        deck["pdf_export"] = self.exports.current(deck_id) if self.exports else None
        return deck

    def sources_used(self, deck_id):
        deck = self.record(deck_id)
        with self.db.connect() as conn:
            return deck_sources.public(conn, deck)

    def rename(self, deck_id, title):
        self.record(deck_id)
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            if conn.execute(
                "SELECT 1 FROM jobs WHERE entity_id=? AND status IN ('queued','running')",
                (deck_id,),
            ).fetchone():
                raise AppError("DECK_BUSY", "Stop or finish the current task before renaming.", 409)
            timestamp = now()
            conn.execute(
                "UPDATE decks SET title=?,title_mode='custom',export_title=CASE WHEN "
                "brief_json IS NULL AND NOT EXISTS "
                "(SELECT 1 FROM pdf_exports WHERE deck_id=decks.id) "
                "THEN ? ELSE export_title END,updated_at=? WHERE id=?",
                (title, title, timestamp, deck_id),
            )
            conn.execute(
                "UPDATE notebooks SET updated_at=? "
                "WHERE id=(SELECT notebook_id FROM decks WHERE id=?)",
                (timestamp, deck_id),
            )
        return self.get(deck_id)

    def list(self, notebook_id):
        NotebookService(self.db).get(notebook_id)
        with self.db.connect() as conn:
            decks = [
                dict(row)
                for row in conn.execute(
                    "SELECT id,title,status,target_slide_count,updated_at,CASE WHEN plan_json "
                    "IS NOT NULL "
                    "THEN (SELECT count(*) FROM slides WHERE deck_id=decks.id) ELSE "
                    "target_slide_count END "
                    "AS slide_count, json_extract(generation_metadata_json,'$.batch_label') "
                    "AS batch_label, (SELECT status FROM jobs WHERE entity_id=decks.id "
                    "ORDER BY status IN ('queued','running') DESC,"
                    "coalesce(finished_at,started_at,created_at) DESC,rowid DESC "
                    "LIMIT 1) AS job_status FROM decks "
                    "WHERE notebook_id=? ORDER BY updated_at DESC,rowid DESC",
                    (notebook_id,),
                )
            ]
            for deck in decks:
                deck["download_available"] = bool(
                    self.exports
                    and deck["job_status"] not in ("queued", "running")
                    and self.exports.downloadable(deck["id"], conn)
                )
        return decks

    def create(self, notebook_id, data):
        NotebookService(self.db).get(notebook_id)
        self._creation_models(data)
        scope, snapshot = self._creation_scope(notebook_id, data)
        with self.db.connect() as conn:
            deck_id = self._insert_creation(conn, notebook_id, data, scope, snapshot)
        return self.get(deck_id)

    def _creation_models(self, data):
        self.models.configured("language")
        if data.render_mode == "generated_page":
            self.models.configured("image")

    def _creation_scope(self, notebook_id, data):
        snapshot = None
        if data.scope.kind == "knowledge":
            page = self.knowledge.get(data.scope.knowledge_page_id)
            if page["notebook_id"] != notebook_id:
                raise AppError("SCOPE_INVALID", "Choose knowledge from this notebook.")
            if not page["content_markdown"] or not page["citations"]:
                raise AppError(
                    "KNOWLEDGE_NOT_GROUNDED",
                    "Choose a knowledge page with original-source citations.",
                )
            snapshot = {
                name: page[name]
                for name in ("id", "title", "content_markdown", "revision", "citations")
            }
            scope = data.scope.model_dump()
        else:
            scope = self.knowledge.freeze(notebook_id, data.scope.source_scope()).model_dump()
        return scope, snapshot

    def _insert_creation(self, conn, notebook_id, data, scope, snapshot, *, label=None, batch=None):
        deck_id, timestamp = uuid4().hex, now()
        manifest = deck_sources.capture(
            conn, scope, snapshot, node_provider=self.knowledge.retrieval.sources.nodes
        )
        title = (
            deck_sources.source_title(manifest)
            if data.title_mode == "source"
            else label or "正在规划 Visual Deck"
        )
        conn.execute(
            "INSERT INTO decks(id,notebook_id,title,source_scope_json,target_slide_count,"
            "language,instruction,knowledge_snapshot_json,generation_metadata_json,created_at,"
            "updated_at,title_mode,export_title,source_manifest_json) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                deck_id,
                notebook_id,
                title,
                json.dumps(scope),
                data.slide_count,
                data.language,
                data.instruction,
                json.dumps(snapshot) if snapshot else None,
                json.dumps(
                    {
                        "generation_version": PAGE_GENERATION_VERSION
                        if data.render_mode == "generated_page"
                        else GENERATION_VERSION,
                        "content_policy_version": CONTENT_POLICY_VERSION,
                        "visual_style_version": STYLE_VERSION,
                        **(batch or {}),
                    }
                ),
                timestamp,
                timestamp,
                data.title_mode,
                title,
                json.dumps(manifest, ensure_ascii=False),
            ),
        )
        self.jobs.enqueue_in_transaction(conn, "deck_generate", deck_id, {"deck_id": deck_id})
        conn.execute("UPDATE notebooks SET updated_at=? WHERE id=?", (timestamp, notebook_id))
        return deck_id

    def create_batch(self, notebook_id, data):
        """Preflight and enqueue the entire batch atomically; retries reuse its identities."""
        NotebookService(self.db).get(notebook_id)
        request = data.model_dump(exclude={"request_key"})
        request_json = json.dumps(request, sort_keys=True)
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute(
                "SELECT * FROM deck_batches WHERE notebook_id=? AND request_key=?",
                (notebook_id, data.request_key),
            ).fetchone()
            if existing:
                saved_request = json.loads(existing["request_json"])
                saved_request.setdefault("title_mode", "auto")
                if saved_request != request:
                    raise AppError(
                        "DECK_BATCH_CONFLICT", "Use a new request key for a changed batch.", 409
                    )
                batch_id, deck_ids = existing["id"], json.loads(existing["deck_ids_json"])
                if any(
                    not conn.execute("SELECT 1 FROM decks WHERE id=?", (identity,)).fetchone()
                    for identity in deck_ids
                ):
                    raise AppError(
                        "DECK_BATCH_DELETED",
                        "A Deck in this batch was deleted. Create a new batch.",
                        409,
                    )
            else:
                self._creation_models(data)
                frozen, snapshot = self._creation_scope(notebook_id, data)
                items = self._batch_items(notebook_id, frozen, snapshot)
                if len(items) > MAX_BATCH_DECKS:
                    raise AppError("DECK_BATCH_LIMIT", "Choose at most 100 Decks per batch.")
                prepared = []
                for scope, label in items:
                    if scope["kind"] != "knowledge" and not any(
                        block["text"].strip()
                        for block in self.knowledge.retrieval.scope_blocks(
                            notebook_id, Scope.model_validate(scope), frozen=True
                        )
                    ):
                        raise AppError(
                            "SOURCE_NO_TEXT", "A chosen section has no readable content."
                        )
                    prepared.append((scope, label))
                batch_id = uuid4().hex
                options = DeckInput.model_validate(request)
                deck_ids = [
                    self._insert_creation(
                        conn,
                        notebook_id,
                        options,
                        scope,
                        snapshot,
                        label=label,
                        batch={
                            "batch_id": batch_id,
                            "batch_label": label,
                            "batch_index": index,
                            "batch_size": len(prepared),
                        },
                    )
                    for index, (scope, label) in enumerate(prepared)
                ]
                conn.execute(
                    "INSERT INTO deck_batches VALUES (?,?,?,?,?,?)",
                    (
                        batch_id,
                        notebook_id,
                        data.request_key,
                        request_json,
                        json.dumps(deck_ids),
                        now(),
                    ),
                )
        return {"batch_id": batch_id, "decks": [self.get(identity) for identity in deck_ids]}

    def _batch_items(self, notebook_id, scope, snapshot):
        if scope["kind"] == "knowledge":
            return [(scope, snapshot["title"])]
        sources = self.knowledge.retrieval.sources.list(notebook_id)
        if scope["kind"] == "selected":
            requested = set(scope["source_ids"])
            return [
                ({"kind": "source", "source_id": source["id"]}, source["title"])
                for source in sources
                if source["id"] in requested
            ]
        source = next(s for s in sources if s["id"] == scope["source_id"])
        if scope["kind"] == "source":
            return [(scope, source["title"])]
        selected = set(scope["node_ids"] if scope["kind"] == "nodes" else [scope["node_id"]])
        return [
            (
                {"kind": "node", "source_id": source["id"], "node_id": node["id"]},
                f"{source['title']} · {node['title']}",
            )
            for node in self.knowledge.retrieval.sources.nodes(source["id"])
            if node["id"] in selected
        ]

    def generated_copy(self, deck_id, *, rewrite_content=False, restyle=None):
        """Reuse saved grounded content; make a new Deck without replacing old outputs."""
        # New content needs a fresh content-adaptive style by default. An explicit
        # False remains available to clients intentionally preserving the old identity.
        if restyle is None:
            restyle = rewrite_content
        deck = self.record(deck_id)
        self.models.configured("image")
        self.models.configured("language")
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            if conn.execute(
                "SELECT 1 FROM jobs WHERE entity_id=? AND status IN ('queued','running')",
                (deck_id,),
            ).fetchone():
                raise AppError("DECK_BUSY", "Wait for this deck's task to finish.", 409)
            rows = conn.execute(
                "SELECT * FROM slides WHERE deck_id=? ORDER BY ordinal", (deck_id,)
            ).fetchall()
            if not rows or not deck["understanding"] or any(not r["spec_json"] for r in rows):
                raise AppError(
                    "DECK_CONTENT_REQUIRED", "Finish all page content before making a copy.", 409
                )
            packets = {e["id"]: e for e in deck["understanding"]["evidence"]}
            for row in rows:
                refs = SlideSpec.model_validate_json(row["spec_json"]).citation_ids()
                if any(ref not in packets for ref in refs) or not all(
                    span["available"]
                    for ref in refs
                    for span in self.citations.preview_spans(packets[ref]["spans"])
                ):
                    raise AppError(
                        "CITATION_SOURCE_UNAVAILABLE", "Restore the original sources first.", 409
                    )
            identity, timestamp = uuid4().hex, now()
            plan = {**deck["plan"], "slides": [json.loads(r["plan_json"]) for r in rows]}
            # Replan standard lengths with fresh research. For manually shortened
            # decks, retain the dossier's IDs so their saved page sequence stays valid.
            replan = rewrite_content and len(rows) in (10, 15, 20)
            conn.execute(
                "INSERT INTO decks(id,notebook_id,title,description,source_scope_json,"
                "target_slide_count,language,instruction,brief_json,plan_json,style_json,"
                "understanding_json,knowledge_snapshot_json,generation_metadata_json,"
                "created_at,updated_at,title_mode,export_title,source_manifest_json) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    identity,
                    deck["notebook_id"],
                    deck["title"],
                    deck["description"],
                    json.dumps(deck["source_scope"]),
                    len(rows) if replan else deck["target_slide_count"],
                    deck["language"],
                    deck["instruction"],
                    None if rewrite_content else json.dumps(deck["brief"]),
                    None if replan else json.dumps(plan),
                    None if restyle else json.dumps(deck["style"]),
                    None if replan else json.dumps(deck["understanding"]),
                    json.dumps(deck["knowledge_snapshot"]) if deck["knowledge_snapshot"] else None,
                    json.dumps(
                        {
                            **{
                                key: value
                                for key, value in (deck["generation_metadata"] or {}).items()
                                if key != "art_direction"
                                and not (restyle and key == "visual_strategy")
                                and not key.startswith("batch_")
                                and not (rewrite_content and key == "content_preferences")
                            },
                            "generation_version": PAGE_GENERATION_VERSION,
                            "copied_from_deck_id": deck_id,
                            "restyled": restyle,
                            **({"visual_style_version": STYLE_VERSION} if restyle else {}),
                            **(
                                {
                                    "content_policy_version": CONTENT_POLICY_VERSION,
                                    "rewritten_content": True,
                                    "replanned_content": replan,
                                }
                                if rewrite_content
                                else {}
                            ),
                        }
                    ),
                    timestamp,
                    timestamp,
                    deck["title_mode"],
                    deck["title"],
                    json.dumps(
                        deck["source_manifest"] or self.sources_used(deck_id), ensure_ascii=False
                    ),
                ),
            )
            for ordinal, row in enumerate([] if replan else rows):
                slide_id = uuid4().hex
                conn.execute(
                    "INSERT INTO slides(id,deck_id,ordinal,plan_json,spec_json,status,revision,"
                    "created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
                    (
                        slide_id,
                        identity,
                        ordinal,
                        row["plan_json"],
                        None if rewrite_content else row["spec_json"],
                        "planned" if rewrite_content else "authored",
                        0 if rewrite_content else 1,
                        timestamp,
                        timestamp,
                    ),
                )
                if not rewrite_content:
                    refs = SlideSpec.model_validate_json(row["spec_json"]).citation_ids()
                    self.citations.persist(
                        conn,
                        deck["notebook_id"],
                        "slide",
                        slide_id,
                        " ".join(f"[[{ref}]]" for ref in refs),
                        [packets[ref] for ref in refs],
                    )
            self.jobs.enqueue_in_transaction(conn, "deck_generate", identity, {"deck_id": identity})
            conn.execute(
                "UPDATE notebooks SET updated_at=? WHERE id=?", (timestamp, deck["notebook_id"])
            )
        return self.get(identity)

    async def pause(self, deck_id):
        self.record(deck_id)
        await self.jobs.cancel_entity(deck_id)
        return self.get(deck_id)

    def resume(self, deck_id):
        deck = self.get(deck_id)
        if deck["job"] and deck["job"]["status"] in ("queued", "running"):
            return deck
        if not deck["job"] or deck["job"]["status"] != "cancelled":
            raise AppError("DECK_NOT_PAUSED", "Only stopped Decks can be resumed.", 409)
        # Reuse the exact job payload (including a pending page revision/export).
        self.jobs.retry(deck["job"]["id"])
        with self.db.connect() as conn:
            conn.execute(
                "UPDATE decks SET status='draft',updated_at=? WHERE id=?", (now(), deck_id)
            )
        return self.get(deck_id)

    async def delete(self, deck_id):
        with self.db.connect() as conn:
            if not conn.execute("SELECT 1 FROM decks WHERE id=?", (deck_id,)).fetchone():
                return
        await self.jobs.cancel_entity(deck_id)
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT notebook_id FROM decks WHERE id=?", (deck_id,)).fetchone()
            if not row:
                return
            conn.execute(
                "DELETE FROM citations WHERE owner_type='slide' AND owner_id IN "
                "(SELECT id FROM slides WHERE deck_id=?)",
                (deck_id,),
            )
            conn.execute("DELETE FROM jobs WHERE entity_id=?", (deck_id,))
            # Cascades queue assets, all render versions and PDFs for durable file cleanup.
            conn.execute("DELETE FROM decks WHERE id=?", (deck_id,))
            conn.execute("UPDATE notebooks SET updated_at=? WHERE id=?", (now(), row[0]))

    def retry(self, deck_id):
        deck = self.get(deck_id)
        if deck["status"] not in ("failed", "partial", "paused"):
            raise AppError("DECK_NOT_RETRYABLE", "Only failed or partial decks need retry.", 409)
        if deck["job"] and deck["job"]["status"] in ("failed", "cancelled"):
            return self.jobs.retry(deck["job"]["id"])
        return self.jobs.enqueue("deck_generate", deck_id, {"deck_id": deck_id})

    def stage(self, deck_id, context, stage, progress):
        context.progress(stage, progress)
        with self.db.connect() as conn:
            conn.execute(
                "UPDATE decks SET status=?,updated_at=? WHERE id=?", (stage, now(), deck_id)
            )

    def retry_slide(self, deck_id, slide_id, without_image=False):
        deck = self.record(deck_id)
        if without_image and uses_generated_pages(deck):
            raise AppError("PAGE_IMAGE_REQUIRED", "A complete page image cannot be skipped.", 409)
        if self.revisions and self.revisions.failed(slide_id):
            return self.revisions.retry(deck_id, slide_id, without_image)
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            slide = conn.execute(
                "SELECT * FROM slides WHERE id=? AND deck_id=?", (slide_id, deck_id)
            ).fetchone()
            if not slide:
                raise AppError("SLIDE_NOT_FOUND", "This slide no longer exists.", 404)
            if conn.execute(
                "SELECT 1 FROM jobs WHERE entity_id=? AND status IN ('queued','running')",
                (deck_id,),
            ).fetchone():
                raise AppError("DECK_BUSY", "Wait for the current deck task to finish.", 409)
            if slide["status"] != "failed":
                raise AppError("SLIDE_NOT_RETRYABLE", "Only failed slides need retry.", 409)
            if without_image:
                changed = conn.execute(
                    "UPDATE assets SET status='skipped',error_code=NULL,error_message=NULL,"
                    "updated_at=? "
                    "WHERE slide_id=? AND status='failed'",
                    (now(), slide_id),
                ).rowcount
                if not changed:
                    raise AppError(
                        "NO_FAILED_IMAGES", "This slide has no failed images to skip.", 409
                    )
            job_id = self.jobs.enqueue_in_transaction(
                conn, "deck_generate", deck_id, {"deck_id": deck_id, "slide_ids": [slide_id]}
            )
        return self.jobs.get(job_id)

    def understanding_from_knowledge(self, deck, context):
        snapshot = deck["knowledge_snapshot"]
        evidence, marker_map = [], {}
        for marker, citation_id in snapshot["citations"].items():
            citation = self.citations.get(citation_id)
            if not citation["available"]:
                raise AppError(
                    "CITATION_SOURCE_UNAVAILABLE",
                    "Original sources for this knowledge page are unavailable. "
                    "Restore them before creating a new deck.",
                )
            new_marker = f"E{context.job['id'][:12]}_{len(evidence) + 1}"
            marker_map[marker] = new_marker
            spans = [
                {name: s[name] for name in ("source_id", "block_id", "start_offset", "end_offset")}
                for s in citation["spans"]
            ]
            evidence.append(
                {
                    "id": new_marker,
                    "text": "\n\n".join(s["quote"] for s in citation["spans"]),
                    "spans": spans,
                }
            )
        content = CITATION_PATTERN.sub(
            lambda match: f"[[{marker_map[match[1]]}]]", snapshot["content_markdown"]
        )
        return {
            "content": content,
            "evidence": evidence,
            "metadata": {
                "knowledge_page_id": snapshot["id"],
                "knowledge_revision": snapshot["revision"],
                "source_ids": sorted(
                    {span["source_id"] for item in evidence for span in item["spans"]}
                ),
            },
        }

    async def preferences(self, deck, *, revision_instruction=""):
        metadata = deck.get("generation_metadata") or {}
        saved = metadata.get("content_preferences")
        if saved is not None and not revision_instruction:
            return DeckPreferences.model_validate(saved)
        preferences = await structured_completion(
            self.models,
            "Resolve deck content preferences. These fields describe presentation preferences, "
            "not permission to invent facts. Explicit user requests override defaults; a "
            "revision_instruction overrides the earlier request only for that page. Set "
            "source_only=true only when the user explicitly restricts content to the supplied "
            "source without outside background or invented examples. Reasoning and close reading "
            "of the supplied passages are still allowed in source-only mode. Otherwise allow "
            "useful "
            "model-knowledge interpretation. Set include_editorial_notes=true only when the "
            "user explicitly asks for author-opinion labels, interpretation-boundary panels, "
            "standalone source notes or similar editorial scaffolding. A request to remove "
            "these labels, or a request for deeper interpretation, does not enable them. "
            "Set dense_text=true only for an explicit request for more visible text per page; "
            "detailed reasoning alone does not require dense layouts. Defaults are all false. "
            "Do not infer a source-only request from the fact that a source was selected. "
            "Set chapter_only=true only when the user explicitly forbids using other chapters "
            "or wider work context (e.g. '只分析本章，不联系全书'). Selecting a chapter or asking "
            "to explain this chapter does not forbid its parent-work context. source_only "
            "forbids outside model knowledge, while supplied uploaded parent-work passages "
            "are still source material unless chapter_only=true. chapter_only defaults false.",
            {
                "user_instruction": deck["instruction"],
                "previous_preferences": saved,
                "revision_instruction": revision_instruction,
            },
            DeckPreferences,
            output_limit=512,
        )
        if not revision_instruction:
            metadata = {**metadata, "content_preferences": preferences.model_dump()}
            with self.db.connect() as conn:
                conn.execute(
                    "UPDATE decks SET generation_metadata_json=? WHERE id=?",
                    (json.dumps(metadata), deck["id"]),
                )
            deck["generation_metadata"] = metadata
        return preferences

    def source_context(self, deck, blocks):
        source_ids = {block["source_id"] for block in blocks}
        scope = deck["source_scope"]
        selected_nodes = set(scope.get("node_ids") or [scope.get("node_id")])
        return [
            {
                "title": source["title"],
                "selected_sections": [
                    node["title"]
                    for node in self.knowledge.retrieval.sources.nodes(source["id"])
                    if node["id"] in selected_nodes
                ],
            }
            for source in self.knowledge.retrieval.sources.list(deck["notebook_id"])
            if source["id"] in source_ids
        ]

    async def understand(self, deck, context):
        if deck["understanding"]:
            return deck["understanding"]
        self.stage(deck["id"], context, "understanding", 0.02)
        preferences = await self.preferences(deck)
        if deck["knowledge_snapshot"]:
            value = self.understanding_from_knowledge(deck, context)
        else:
            blocks = self.knowledge.retrieval.scope_blocks(
                deck["notebook_id"], Scope.model_validate(deck["source_scope"]), frozen=True
            )
            work, background_evidence, work_metadata = await self.work_context.build(
                deck,
                blocks,
                context.substage("understanding", 0.02, 0.10),
                chapter_only=preferences.chapter_only,
            )
            content, evidence, metadata = await self.knowledge.synthesis.run(
                blocks,
                context.substage("understanding", 0.10, 0.16),
                purpose="deck",
                instruction=deck["instruction"],
                source_context=self.source_context(deck, blocks),
                preferences=preferences.model_dump(),
                work_context=work,
            )
            value = {
                "content": content,
                "evidence": [*evidence, *background_evidence],
                "metadata": {**metadata, "work_context": work_metadata},
                "work_context": work,
            }
        with self.db.connect() as conn:
            conn.execute(
                "UPDATE decks SET understanding_json=? WHERE id=?", (json.dumps(value), deck["id"])
            )
        deck["understanding"] = value
        return value

    async def plan(self, deck, understanding, context):
        self.stage(deck["id"], context, "planning", 0.18)
        preferences = await self.preferences(deck)
        if not deck["brief"]:

            def check_brief(value):
                if (
                    value.slide_count != deck["target_slide_count"]
                    or value.language != deck["language"]
                ):
                    raise ValueError(
                        f"slide_count must equal {deck['target_slide_count']} and language "
                        f"must equal the exact code {deck['language']!r}, without translation "
                        "or additional labels"
                    )

            brief = await structured_completion(
                self.models,
                "Create a DeckBrief. "
                + GROUNDING
                + CONTENT_POLICY
                + WORK_CONTEXT_POLICY
                + "Infer topic, goal and audience from the source and optional "
                "user instruction. Preserve requested length and language. "
                "The language field must contain the exact supplied language code, "
                "without translation or additional labels.",
                {
                    "understanding": understanding["content"],
                    "slide_count": deck["target_slide_count"],
                    "language": deck["language"],
                    "user_instruction": deck["instruction"],
                    "preferences": preferences.model_dump(),
                    "work_context": understanding.get("work_context", {}),
                },
                DeckBrief,
                validate=check_brief,
                error_code="DECK_PLAN_INVALID",
            )
            deck["brief"] = brief.model_dump()
            with self.db.connect() as conn:
                conn.execute(
                    "UPDATE decks SET brief_json=?,title=CASE WHEN title_mode='auto' THEN ? "
                    "ELSE title END,export_title=CASE WHEN title_mode='auto' THEN ? "
                    "ELSE export_title END,description=? WHERE id=?",
                    (brief.model_dump_json(), brief.topic, brief.topic, brief.goal, deck["id"]),
                )
        if not deck["plan"]:
            cited = set(CITATION_PATTERN.findall(understanding["content"]))
            background = set(understanding.get("work_context", {}).get("evidence_ids", []))
            catalog = [
                {
                    "id": e["id"],
                    "role": "whole_work" if e["id"] in background else "selected_material",
                    "text": e["text"][:600],
                }
                for e in understanding["evidence"]
                if e.get("spans") and e["id"] in cited | background
            ]
            allowed = {e["id"] for e in catalog}

            def check_plan(value):
                if [slide.index for slide in value.slides] != list(
                    range(1, deck["target_slide_count"] + 1)
                ):
                    raise ValueError("Return exactly the requested slide count in order")
                invalid = [
                    (i, set(s.evidence_ids) - allowed)
                    for i, s in enumerate(value.slides)
                    if set(s.evidence_ids) - allowed
                ]
                if invalid:
                    raise EvidenceValidationError(
                        [["slides", i, "evidence_ids"] for i, _ in invalid],
                        set().union(*(ids for _, ids in invalid)),
                        allowed,
                    )
                if any(not s.teaching_points or not s.visual_concept.strip() for s in value.slides):
                    raise ValueError("Every page needs specific teaching_points and visual_concept")
                if any(
                    not s.visual_grammar.strip()
                    or not 40 <= s.reading_budget <= (900 if preferences.dense_text else 450)
                    for s in value.slides
                ):
                    raise ValueError(
                        "Every new page needs a visual_grammar and a reading_budget "
                        f"of 40-{900 if preferences.dense_text else 450} display units"
                    )
                messages = [s.key_message.strip() for s in value.slides]
                if len(set(messages)) != len(messages):
                    raise ValueError("Each page must advance a distinct message, without padding")

            plan = await structured_completion(
                self.models,
                "Plan the narrative for a Visual Deck. "
                + GROUNDING
                + CONTENT_POLICY
                + WORK_CONTEXT_POLICY
                + "Build an intentional learning sequence with exactly the "
                "requested total number of pages. "
                "Do not divide the document into equal slices or repeat a fixed slide pattern. "
                "Give each slide one major message, purpose and source evidence "
                "IDs from citable_evidence. Whole-work IDs are valid background references; "
                "keep the selected chapter central and never present background as chapter words. "
                "Include opening and closing within the total. "
                "Adapt explanations, comparisons, quotations and conceptual "
                "transitions to the actual material. "
                "Plan substantive teaching, not a succession of vague claims. Specify 1-4 "
                "specific teaching_points per page: mechanisms, contrasts, examples, "
                "findings or short quotations that make its message understandable. "
                "Include methods only when they advance the source's message. Keep original "
                "factual scope beside its claim. Develop requested interpretation and "
                "model-knowledge "
                "explanations as real content; do not allocate most pages to retelling events. "
                "For paragraph-by-paragraph requests, map the selected key passages in order and "
                "pair quotations with useful explanations. A supplied evidence ID may anchor an "
                "interpretation, but cannot prove outside background or an invented example. "
                "Plan a visual storyboard across the WHOLE deck. Each visual_concept must "
                "describe what the reader sees, which conceptual relation it explains and "
                "where text fits. Choose illustration, diagram or typography per page. "
                + (
                    "Image generation supports photographic, graphic, diagrammatic, typographic "
                    "and painterly pages equally. Choose visual methods by explanatory purpose; "
                    "do not mandate illustrations, scenery or an immersive cover. Visual "
                    "concepts are provisional: later content-adaptive art direction chooses "
                    "the medium. "
                    if adaptive_style(deck)
                    else "When image generation is available, use substantial custom illustrations "
                    "on several meaningful pages (including an evocative opening), not just "
                    "one tiny icon. "
                )
                + "Alternate visual scale and composition; avoid a repeated "
                "timeline/card grid. Images must explain or embody the subject, not imply "
                "unsupported measurements. Prefer 2-4 relevant evidence IDs per page. "
                "Keep this storyboard compact: teaching points are short phrases, and each "
                "visual concept is 1-2 sentences. Do not write finished body copy here; "
                "the page author will develop it from the original evidence. "
                "For each page, visual_grammar states the explanatory relationship and its spatial "
                "reading: boundary/crossing, stages, mechanism, contrast, nested spaces, "
                "cycle, annotated metaphor or an immersive statement. This is NOT a template "
                "name. Image-plus-text is not itself a visual grammar. Keep the picture/diagram "
                "as the primary explanation on visually led pages. Specify reading_budget in "
                "display units (one CJK character or Latin word): usually 160-320, at most 450 "
                "unless preferences.dense_text=true explicitly requests denser pages "
                "(then up to 900), "
                "40-120 on cover/transition/closing. Visual labels replace redundant paragraphs. "
                "Budget includes every visible title, label, quote, caption and note. Preserve "
                "essential qualifiers; omit side issues rather than shrinking typography.",
                {
                    "brief": deck["brief"],
                    "citable_evidence": catalog,
                    "understanding": understanding["content"],
                    "user_instruction": deck["instruction"],
                    "preferences": preferences.model_dump(),
                    "work_context": understanding.get("work_context", {}),
                    "image_generation_available": bool(
                        self.models.public_configs()["models"].get("image")
                    ),
                },
                DeckPlan,
                output_limit=8000,
                validate=check_plan,
                error_code="DECK_PLAN_INVALID",
            )
            deck["plan"] = plan.model_dump()
            with self.db.connect() as conn:
                conn.execute(
                    "UPDATE decks SET plan_json=? WHERE id=?", (plan.model_dump_json(), deck["id"])
                )
                for slide in plan.slides:
                    conn.execute(
                        "INSERT INTO "
                        "slides(id,deck_id,ordinal,plan_json,created_at,updated_at) "
                        "VALUES (?,?,?,?,?,?)",
                        (
                            uuid4().hex,
                            deck["id"],
                            slide.index - 1,
                            slide.model_dump_json(),
                            now(),
                            now(),
                        ),
                    )
        return deck["brief"], deck["plan"]

    async def style(self, deck, context):
        if deck["style"]:
            return deck["style"]
        self.stage(deck["id"], context, "styling", 0.3)
        style = await structured_completion(
            self.models,
            STYLE_SYSTEM
            if adaptive_style(deck)
            else "Define a unique DeckStyleManifest. "
            + GROUNDING
            + "Invent a coherent visual language for this specific content. Do "
            "not select a template or preset theme. "
            "Define a meaningful design concept, palette, typography "
            "direction, composition, image style, motifs, density and "
            "consistency rules. "
            "Ensure readable foreground/background contrast. Layout may vary "
            "within one recognizable visual system. "
            "In composition.rhythm, include concise slide-indexed art directions for reading "
            "surface and visual scale so page authors can coordinate light, dark and immersive "
            "pages across the deck. Avoid framing every illustration in an identical pale page. "
            "Images should support understanding, visual metaphors and "
            "memory, not merely decoration. "
            "Art-direct an editorial illustrated essay with a subject-specific visual world, "
            "not generic corporate cards and nodes. Describe tactile materials, lighting, "
            "depth and reusable visual symbolism. Rhythm must vary: immersive opening, "
            "explanatory scenes, comparisons, quotation and synthesis where justified. "
            "Allow light and dark backgrounds from one palette, plus large illustrations "
            "and text-free illustrated backdrops with calm reading zones. Consistency "
            "means typography, palette and visual vocabulary, not identical backgrounds "
            "or a decorative line on every page. Font family names must use installed "
            "Latin names such as Noto Serif CJK SC or Noto Sans CJK SC. "
            "Titles should be bold and concise; body should be readable at presentation scale. "
            "Consistency rules should encode visual materials, stroke/label treatment, lighting "
            "and metaphor vocabulary. Do not require the same scenic subject on every page. "
            "Use each page visual_grammar to build different explanatory visuals, not the same "
            "landscape illustration plus a prose column fifteen times."
            + (
                " This Deck uses whole-page image generation INCLUDING typography. Describe "
                "one visual world for completed illustrated pages with integrated labels; "
                "never require text-free artwork or later native text overlays. "
                "Specify drawing character, material, typography and color meaning as invariants, "
                "not a recurring scene or fixed frame. A subsequent whole-deck art direction "
                "will select individual surfaces and compositions. Do not equate gaming or "
                "technology with constant blue glow, glass UI cards or neon landscapes."
                if uses_generated_pages(deck)
                else ""
            ),
            style_data(deck, whole_page_images=uses_generated_pages(deck))
            if adaptive_style(deck)
            else {"brief": deck["brief"], "plan": deck["plan"]},
            AdaptiveDeckStyle if adaptive_style(deck) else DeckStyleManifest,
            output_limit=6000 if adaptive_style(deck) else 4096,
            validate=validate_style if adaptive_style(deck) else None,
        )
        metadata = deck.get("generation_metadata") or {}
        if isinstance(style, AdaptiveDeckStyle):
            metadata = {**metadata, "visual_strategy": style.strategy.model_dump()}
            style = style.style
        with self.db.connect() as conn:
            conn.execute(
                "UPDATE decks SET style_json=?,generation_metadata_json=? WHERE id=?",
                (style.model_dump_json(), json.dumps(metadata), deck["id"]),
            )
        deck["generation_metadata"] = metadata
        deck["style"] = style.model_dump()
        return deck["style"]

    async def author(self, *args, **kwargs):
        async with self.knowledge.synthesis.content_budget.slot(CONTENT_CONCURRENCY.get()):
            return await self._author(*args, **kwargs)

    async def _author(
        self, deck, understanding, row, context, *, instruction="", previous=None, persist=True
    ):
        planned = json.loads(row["plan_json"])
        preferences = await self.preferences(deck, revision_instruction=instruction)
        packets = {e["id"]: e for e in understanding["evidence"]}
        evidence = [packets[identity] for identity in planned["evidence_ids"]]
        if not all(
            span["available"]
            for item in evidence
            for span in self.citations.preview_spans(item["spans"])
        ):
            raise AppError(
                "CITATION_SOURCE_UNAVAILABLE",
                "Restore the original sources before regenerating content.",
                409,
            )
        allowed = {e["id"] for e in evidence}
        all_source_images = bind_visuals(
            evidence,
            await joined_thread(self.knowledge.synthesis.visuals.for_evidence, evidence),
        )
        source_images = all_source_images[:MAX_IMAGES]

        def check_spec(value):
            if any(VISUAL_PLACEHOLDER in f["text"] for f in content_fragments(value)):
                raise ValueError(
                    "Do not display the internal image placeholder; explain actual pixels"
                )
            check_source_content(
                value, evidence, include_editorial_notes=preferences.include_editorial_notes
            )
            check_content_basis(value, source_only=preferences.source_only)
            if (
                not previous
                and planned.get("visual_mode") == "illustration"
                and not value.asset_requests
                and not uses_generated_pages(deck)
            ):
                raise ValueError("The storyboard requires an explanatory illustration asset")
            if not value.citation_ids():
                raise ValueError("The page needs at least one supplied original-source citation")
            unsupported = set(value.citation_ids()) - allowed
            if unsupported:
                raise ValueError(
                    f"Unsupported page citations: {sorted(unsupported)}. "
                    f"Only these evidence IDs are citable on this page: {sorted(allowed)}. "
                    "The dossier and whole-work map are explanatory context, not extra evidence."
                )
            original = "\n".join(e["text"] for e in evidence)
            if any(
                match.group() not in original
                for fragment in content_fragments(value)
                for match in CITATION_PATTERN.finditer(fragment["text"])
            ):
                raise ValueError(
                    "Move evidence markers from visible text into citations fields only."
                )
            budget = planned.get("reading_budget", 0)
            if budget:
                units = sum(
                    len(re.findall(r"[\u3400-\u9fff]|[\w]+", fragment["text"]))
                    for fragment in content_fragments(value)
                )
                # The storyboard budget is an art-direction target. A small counting margin
                # avoids failing for a few characters; the global ceiling stays strict.
                ceiling = min(900 if preferences.dense_text else 450, math.ceil(budget * 1.08))
                if units > ceiling:
                    raise FieldValidationError(
                        f"Visible copy exceeds reading_budget: {units} units versus {budget}. "
                        f"Aim for at most {int(budget * 0.8)} display units TOTAL, counting "
                        "EVERY title, label, quote, item and explanation. Shorten the affected "
                        "copy; preserve core evidence, qualifiers and exact quoted wording. "
                        "Keep key_message (internal) and evidence IDs unchanged.",
                        [["content_elements"], ["visual_relationships"]],
                        progress=units - ceiling,
                        details={
                            "target_units": int(budget * 0.75),
                            "ceiling": ceiling,
                            "visible_fragments": [
                                {
                                    "id": f["id"],
                                    "units": len(re.findall(r"[\u3400-\u9fff]|[\w]+", f["text"])),
                                }
                                for f in content_fragments(value)
                            ],
                        },
                    )

        spec = await structured_completion(
            self.models,
            "Author one SlideSpec for a Visual Deck. "
            + GROUNDING
            + CONTENT_POLICY
            + WORK_CONTEXT_POLICY
            + "Follow the narrative purpose and deck-level style. Write "
            "succinct, readable semantic content in the requested language. "
            "Use varied semantic elements (statement, comparison, quote, "
            "number, labels, lists) when they improve understanding. "
            "Do not reduce every slide to a title, bullets and an image. Do "
            "not output pixel positions or a fixed template. "
            "Decide hierarchy, balance, white space, emphasis and mood. "
            "hierarchy must reference element IDs. "
            "Develop the planned teaching_points with specific explanation and relevant model "
            "knowledge, following the user's requested depth and the resolved preferences. "
            "do not merely paraphrase the headline or repeat a generic evidence warning. "
            "A normal explanatory page should contain 2-4 meaningful, concise content "
            "pieces, such as a mechanism plus a source example, or an actual quotation. "
            "Use natural subject-specific labels. Explain why, how, implications and conceptual "
            "links; a plot retelling or quote paraphrase alone is not a deep interpretation. "
            "For a requested close reading, pair the passage with substantive reasoning. "
            + (
                "Opening pages should suit the chosen visual medium and be concise: "
                if adaptive_style(deck)
                else "Opening pages should be visually immersive and concise: "
            )
            + "a strong title and one brief context sentence. "
            "Save detailed mechanisms and comparisons for later pages "
            "rather than crowding the cover. When quoting in translation, label it as a "
            "translation; do not put an invented paraphrase in quotation marks. "
            + (
                "The entire page, including text, will be painted by one image model. "
                "Set asset_requests to []: no separate illustration assets are needed. "
                "Specify the complete explanatory visual in visual_direction. Prefer a concise "
                "headline, short labels and concrete short explanations that can be rendered "
                "accurately in an integrated image; preserve essential factual qualifiers. "
                if uses_generated_pages(deck)
                else "Follow the storyboard visual_concept; an illustration page MUST request "
                "a major image with specified subject, conceptual relationship and quiet "
                "regions for separately rendered text. It may be an immersive backdrop or "
                "large diagrammatic scene. Never embed readable words into image assets. "
            )
            + "Execute visual_grammar: make labels and concise explanations attach to the "
            "actual visual mechanism, rather than separating a long essay from an illustration. "
            "Use visual_relationships for actual or interpreted connections between distinct "
            "content elements (sequence, contrast, association, cause or cycle). Do not convert "
            "mere association into an established cause. Relationships "
            "must not connect an element to itself except for a genuine cycle. Describe a "
            "sequence inside one list in visual_direction, not as a self-referencing edge. "
            "guide the visual explanation. Include a relationship only "
            "when it improves explanation. Observe reading_budget for ALL visible "
            "copy, including EVERY title, label, item, quotation and caption. Aim for 75% "
            "of that maximum to leave room for labels; it is a ceiling, not a target to fill. "
            "Allocate this total BEFORE drafting: about 10% title, 25% exact passage and "
            "65% substantive explanation for a close-reading page; when not quoting, use "
            "the passage allocation for explanation. Do not duplicate the same claim in "
            "headline, label, body and summary. Prefer fewer developed explanations over "
            "many shallow fragments. Comparison and bullet_list elements require items; "
            "a standalone explanatory paragraph uses body or statement with text. "
            "Write concise labels plus concrete "
            "mechanisms and useful explanations, avoiding unsolicited editorial scaffolding. "
            "Only request generated images when they explain a concept or "
            "serve the narrative. Each asset request needs a purpose and "
            "subject. "
            "Set each element/item/relationship's internal basis: source for actual source "
            "content; interpretation for a reading of supplied passages; background for model "
            "knowledge; analogy for an invented illustrative example. Items may inherit the "
            "parent basis. Source facts and interpretations cite supplied evidence IDs; those "
            "IDs anchor an interpretation without implying it is literally stated. Background "
            "and invented examples MUST NOT carry or inherit source citations. Illustrative "
            "examples are allowed, but phrase them as examples ('imagine', '比如') rather than "
            "reported events or measurements. Quotes must be actual source content with basis "
            "source. Never fabricate numbers, quotations or references. basis is internal "
            "Only the evidence list supplies citable IDs for this page. The full dossier and "
            "work_context guide interpretation, but cannot supply extra IDs or quotations. "
            "Keep IDs in citations fields; do not put [[E...]] markers into visible text. "
            "metadata, never a visible heading. When preferences.source_only=true, use only "
            "source and source-grounded interpretation; omit background and analogy. "
            "User revision requests take precedence for this page. "
            "When revising, use previous_slide as context and apply revision_instruction only "
            "to this slide. Preserve its narrative purpose and the deck-wide style.",
            {
                "brief": deck["brief"],
                "user_instruction": deck["instruction"],
                "preferences": preferences.model_dump(),
                "narrative": deck["plan"]["narrative"],
                "source_context": page_context(understanding["content"], allowed),
                "work_context": page_context(understanding.get("work_context", {}), allowed),
                "slide_plan": planned,
                "copy_constraints": {
                    "target_units": int(planned.get("reading_budget", 0) * 0.75),
                    "count_all_titles_labels_items_quotes": True,
                    "keep_opening_and_closing_brief": planned["index"]
                    in (1, deck["target_slide_count"]),
                    "preferred_content_elements": 2
                    if planned["index"] == 1
                    else 3
                    if planned["index"] == deck["target_slide_count"]
                    else 4,
                    "defer_detailed_close_reading_to_body_pages": planned["index"]
                    in (1, deck["target_slide_count"]),
                },
                "adjacent_pages": [
                    {"title": s["title"], "key_message": s["key_message"]}
                    for s in deck["plan"]["slides"]
                    if abs(s["index"] - planned["index"]) == 1
                ],
                "style": deck["style"],
                "evidence": [{"id": e["id"], "text": e["text"]} for e in evidence],
                "revision_instruction": instruction,
                "previous_slide": previous,
                **(
                    {
                        "additional_source_images_not_reattached": visual_manifest(
                            all_source_images[MAX_IMAGES:]
                        )
                    }
                    if len(all_source_images) > MAX_IMAGES
                    else {}
                ),
            },
            SlideSpec,
            output_limit=6000,
            validate=check_spec,
            error_code="DECK_PAGE_INVALID",
            subject_id=row["id"],
            max_attempts=3,
            repair_format="auto",
            diagnose=lambda candidate: diagnose_page(
                candidate,
                allowed=allowed,
                budget=planned.get("reading_budget", 0),
                dense=preferences.dense_text,
                source_only=preferences.source_only,
            ),
            source_images=source_images,
        )
        if not persist:
            return spec, evidence
        with self.db.connect() as conn:
            conn.execute(
                "UPDATE slides SET "
                "spec_json=?,status='authored',revision=revision+1,"
                "error_code=NULL,error_message=NULL,updated_at=? WHERE id=?",
                (spec.model_dump_json(), now(), row["id"]),
            )
            self.citations.persist(
                conn,
                deck["notebook_id"],
                "slide",
                row["id"],
                " ".join(f"[[{marker}]]" for marker in spec.citation_ids()),
                evidence,
            )

    async def render_page(self, deck, slide):
        design = (
            await self.composition.prepare_design(deck, slide)
            if hasattr(self.composition, "prepare_design")
            else None
        )
        assets = await self.assets.prepare(deck, slide, design=design) if self.assets else {}
        await self.composition.render_slide(deck, slide, assets)

    async def generate(self, payload, context):
        deck = self.record(payload["deck_id"])
        # Snapshot before the first model request. UI changes apply to subsequent runs.
        concurrency = (
            self.image_generation_settings.get()["concurrency"] if uses_generated_pages(deck) else 1
        )
        content_concurrency = self.content_generation_settings.get()["concurrency"]
        concurrency_token = CONTENT_CONCURRENCY.set(content_concurrency)
        try:
            understanding = await self.understand(deck, context)
            await self.plan(deck, understanding, context)
            await self.style(deck, context)
            with self.db.connect() as conn:
                rows = conn.execute(
                    "SELECT * FROM slides WHERE deck_id=? ORDER BY ordinal", (deck["id"],)
                ).fetchall()
            failed = []
            pending = [
                row
                for row in rows
                if not row["spec_json"]
                and (not payload.get("slide_ids") or row["id"] in payload["slide_ids"])
            ]
            completed_authors = 0

            async def author_page(index, row):
                nonlocal completed_authors
                try:
                    await self.author(deck, understanding, row, context)
                except AppError as error:
                    failed.append(row["id"])
                    with self.db.connect() as conn:
                        conn.execute(
                            "UPDATE slides SET status='failed',error_code=?,error_message=?,"
                            "updated_at=? WHERE id=?",
                            (error.code, error.message, now(), row["id"]),
                        )
                completed_authors += 1
                self.stage(
                    deck["id"], context, "authoring", 0.4 + 0.3 * completed_authors / len(pending)
                )

            self.stage(deck["id"], context, "authoring", 0.4)
            await bounded_map(pending, author_page, content_concurrency)
            with self.db.connect() as conn:
                authored_rows = conn.execute(
                    "SELECT * FROM slides WHERE deck_id=? ORDER BY ordinal", (deck["id"],)
                ).fetchall()
            missing = [row["id"] for row in authored_rows if not row["spec_json"]]
            if missing and uses_generated_pages(deck):
                with self.db.connect() as conn:
                    conn.execute(
                        "UPDATE decks SET status='partial',revision=revision+1,"
                        "generation_metadata_json=?,updated_at=? WHERE id=?",
                        (
                            json.dumps(
                                {
                                    **(deck.get("generation_metadata") or {}),
                                    **understanding["metadata"],
                                    "image_generation_concurrency": concurrency,
                                    "content_generation_concurrency": content_concurrency,
                                }
                            ),
                            now(),
                            deck["id"],
                        ),
                    )
                return {
                    "deck_id": deck["id"],
                    "failed_slide_ids": missing,
                    "content_complete": False,
                }
            await self.art.prepare(deck, authored_rows, context)
            if self.composition:
                with self.db.connect() as conn:
                    renderable = conn.execute(
                        "SELECT * FROM slides WHERE deck_id=? "
                        "AND spec_json IS NOT NULL ORDER BY ordinal",
                        (deck["id"],),
                    ).fetchall()
                renderable = [
                    s
                    for s in renderable
                    if not payload.get("slide_ids") or s["id"] in payload["slide_ids"]
                ]
                semaphore = asyncio.Semaphore(concurrency)
                completed = 0

                async def render_page(slide):
                    nonlocal completed
                    async with semaphore:
                        progress = 0.75 + 0.23 * completed / len(renderable)
                        self.stage(deck["id"], context, "generating_assets", progress)
                        try:
                            async with self.render_budget.slot(concurrency):
                                await self.render_page(deck, slide)
                        except AppError as error:
                            failed.append(slide["id"])
                            with self.db.connect() as conn:
                                conn.execute(
                                    "UPDATE slides SET status='failed',"
                                    "error_code=?,error_message=? WHERE id=?",
                                    (error.code, error.message, slide["id"]),
                                )
                        completed += 1
                        self.stage(
                            deck["id"],
                            context,
                            "rendering",
                            0.75 + 0.23 * completed / len(renderable),
                        )

                # TaskGroup cancels and awaits every sibling on interruption/unexpected error.
                # A normal provider failure is isolated to its page, which remains retryable.
                async with asyncio.TaskGroup() as group:
                    for slide in renderable:
                        group.create_task(render_page(slide))
            with self.db.connect() as conn:
                failed = [
                    r[0]
                    for r in conn.execute(
                        "SELECT id FROM slides WHERE deck_id=? AND status='failed' "
                        "ORDER BY ordinal",
                        (deck["id"],),
                    )
                ]
            exported = False
            if not failed and self.composition and self.exports:
                await self.exports.build(deck["id"], context.substage("exporting", 0.98, 1))
                exported = True
            with self.db.connect() as conn:
                conn.execute(
                    "UPDATE decks SET "
                    "status=?,revision=revision+1,generation_metadata_json=?,"
                    "updated_at=? WHERE id=?",
                    (
                        "partial" if failed else "ready" if exported else "draft",
                        json.dumps(
                            {
                                **(deck.get("generation_metadata") or {}),
                                "image_generation_concurrency": concurrency,
                                "content_generation_concurrency": content_concurrency,
                                "generation_version": (deck.get("generation_metadata") or {}).get(
                                    "generation_version", "deck-content-v2"
                                ),
                                **understanding["metadata"],
                            }
                        ),
                        now(),
                        deck["id"],
                    ),
                )
            return {
                "deck_id": deck["id"],
                "failed_slide_ids": failed,
                "content_complete": not failed,
            }
        except Exception:
            with self.db.connect() as conn:
                conn.execute(
                    "UPDATE decks SET status='failed',updated_at=? WHERE id=?", (now(), deck["id"])
                )
            raise
        finally:
            CONTENT_CONCURRENCY.reset(concurrency_token)
