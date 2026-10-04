from __future__ import annotations

import asyncio
import hashlib
import json
import shutil
import sqlite3
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

from fastapi import UploadFile

from .concurrency import joined_thread
from .config import Settings
from .db import Database
from .documents import Document, DocumentBlock, stable_id
from .docx_parser import DOCX_PARSER_VERSION, DocxParser
from .embedding_identity import index_signature
from .epub import PARSER_VERSION, EpubParser
from .errors import AppError
from .jobs import JobContext, JobService
from .maintenance import discard_source_caches
from .model_service import now
from .notebooks import NotebookService
from .passages import project_passages, raw_passages, select_passages
from .pdf_parser import PDF_PARSER_VERSION, PdfParser
from .reading import pdf_reading, raw_reading
from .text_parsers import MARKDOWN_PARSER_VERSION, TEXT_PARSER_VERSION, MarkdownParser, TextParser
from .web_fetch import WebFetcher, normalize_web_url
from .web_images import WEB_IMAGES_VERSION, WebImageService
from .web_parser import WEB_PARSER_VERSION, WebParser


class SourceService:
    def __init__(self, db: Database, settings: Settings, jobs: JobService):
        self.db, self.settings, self.jobs = db, settings, jobs
        self.notebooks = NotebookService(db)
        self.indexer = None
        self.vision = None
        self.toc_cache = {}
        self.web_fetcher = WebFetcher(
            settings.max_web_bytes,
            settings.web_fetch_timeout,
            fake_ip_fallback=settings.web_fake_ip_dns_fallback,
        )
        self.web_images = WebImageService(settings)
        self.parser = EpubParser(
            max_entries=settings.max_epub_entries,
            max_uncompressed_bytes=settings.max_epub_uncompressed_bytes,
            max_entry_bytes=settings.max_epub_entry_bytes,
            max_compression_ratio=settings.max_epub_compression_ratio,
        )
        self.parsers = {
            "epub": (PARSER_VERSION, self.parser),
            "pdf": (
                PDF_PARSER_VERSION,
                PdfParser(
                    settings.max_pdf_pages, settings.min_pdf_text_characters, include_images=True
                ),
            ),
            "markdown": (MARKDOWN_PARSER_VERSION, MarkdownParser()),
            "text": (TEXT_PARSER_VERSION, TextParser()),
            "docx": (DOCX_PARSER_VERSION, DocxParser(self.parser)),
            "web": (WEB_PARSER_VERSION, WebParser(settings.max_web_images)),
        }
        jobs.handlers["source_ingest"] = self.ingest
        jobs.handlers["source_web_images"] = self.enrich_web_images

    def get(self, source_id: str) -> dict:
        with self.db.connect() as conn:
            row = conn.execute("SELECT * FROM sources WHERE id=?", (source_id,)).fetchone()
        if not row:
            raise AppError("SOURCE_NOT_FOUND", "Original source unavailable.", 404)
        result = dict(row)
        result["metadata"] = json.loads(result.pop("metadata_json"))
        result.pop("file_uri")
        with self.db.connect() as conn:
            job = conn.execute(
                "SELECT id FROM jobs WHERE entity_id=? ORDER BY status IN "
                "('queued','running') DESC,created_at DESC,rowid DESC LIMIT 1",
                (source_id,),
            ).fetchone()
        result["job"] = self.jobs.get(job[0]) if job else None
        return result

    def list(self, notebook_id: str) -> list[dict]:
        self.notebooks.get(notebook_id)
        with self.db.connect() as conn:
            refs = conn.execute(
                "SELECT source_id, enabled, ordinal FROM notebook_sources "
                "WHERE notebook_id=? ORDER BY ordinal",
                (notebook_id,),
            ).fetchall()
        return [
            {
                **self.get(row["source_id"]),
                "enabled": bool(row["enabled"]),
                "ordinal": row["ordinal"],
            }
            for row in refs
        ]

    def attach(self, notebook_id: str, source_id: str) -> dict:
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            if not conn.execute("SELECT 1 FROM notebooks WHERE id=?", (notebook_id,)).fetchone():
                raise AppError("NOTEBOOK_NOT_FOUND", "This notebook no longer exists.", 404)
            if not conn.execute("SELECT 1 FROM sources WHERE id=?", (source_id,)).fetchone():
                raise AppError("SOURCE_NOT_FOUND", "Original source unavailable.", 404)
            existing = conn.execute(
                "SELECT 1 FROM notebook_sources WHERE notebook_id=? AND source_id=?",
                (notebook_id, source_id),
            ).fetchone()
            if not existing:
                count = conn.execute(
                    "SELECT count(*) FROM notebook_sources WHERE notebook_id=?", (notebook_id,)
                ).fetchone()[0]
                if count >= self.settings.max_sources_per_notebook:
                    raise AppError(
                        "SOURCE_LIMIT", "This notebook has reached its source limit.", 409
                    )
                ordinal = conn.execute(
                    "SELECT coalesce(max(ordinal),-1)+1 FROM notebook_sources WHERE notebook_id=?",
                    (notebook_id,),
                ).fetchone()[0]
                conn.execute(
                    "INSERT INTO notebook_sources VALUES (?,?,?,1,?)",
                    (notebook_id, source_id, ordinal, now()),
                )
                conn.execute("UPDATE notebooks SET updated_at=? WHERE id=?", (now(), notebook_id))
            # Detached sources are excluded from model-switch rebuilds. Relinking an
            # old source must bring its index into the current space without parsing.
            if self.indexer and self.indexer.models.indexes:
                model = self.indexer.models.public_configs()["models"].get("embedding")
                if model:
                    self.indexer.models.indexes.enqueue_in_transaction(
                        conn, index_signature(model), source_ids={source_id}
                    )
        return self.get(source_id)

    def set_enabled(self, notebook_id: str, source_id: str, enabled: bool) -> dict:
        with self.db.connect() as conn:
            changed = conn.execute(
                "UPDATE notebook_sources SET enabled=? WHERE notebook_id=? AND source_id=?",
                (int(enabled), notebook_id, source_id),
            ).rowcount
        if not changed:
            raise AppError("SOURCE_NOT_IN_NOTEBOOK", "This source is not in the notebook.", 404)
        return {"enabled": enabled}

    def detach(self, notebook_id: str, source_id: str) -> None:
        with self.db.connect() as conn:
            changed = conn.execute(
                "DELETE FROM notebook_sources WHERE notebook_id=? AND source_id=?",
                (notebook_id, source_id),
            ).rowcount
        if not changed:
            raise AppError("SOURCE_NOT_IN_NOTEBOOK", "This source is not in the notebook.", 404)

    async def upload(self, notebook_id: str, file: UploadFile) -> dict:
        self.notebooks.get(notebook_id)
        filename = (file.filename or "source").replace("\\", "/").rsplit("/", 1)[-1]
        extension = Path(filename).suffix.lower()
        formats = {
            ".epub": ("epub", "application/epub+zip"),
            ".pdf": ("pdf", "application/pdf"),
            ".md": ("markdown", "text/markdown"),
            ".markdown": ("markdown", "text/markdown"),
            ".txt": ("text", "text/plain"),
            ".docx": (
                "docx",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ),
        }
        if extension not in formats:
            raise AppError(
                "SOURCE_TYPE_UNSUPPORTED",
                "Supported source formats are EPUB, PDF, Word (.docx), Markdown and TXT.",
            )
        source_type, mime_type = formats[extension]
        max_bytes = (
            self.settings.max_text_bytes
            if source_type in ("markdown", "text")
            else self.settings.max_document_bytes
        )
        temp = self.settings.data_dir / "cache" / f"upload-{uuid4().hex}"
        digest, size = hashlib.sha256(), 0
        try:
            with temp.open("wb") as output:
                while data := await file.read(1024 * 1024):
                    size += len(data)
                    if size > max_bytes:
                        raise AppError(
                            "SOURCE_TOO_LARGE",
                            "The source exceeds the configured file size limit.",
                            413,
                        )
                    digest.update(data)
                    output.write(data)
            if not size:
                raise AppError("SOURCE_EMPTY", "The uploaded file is empty.")
            checksum = digest.hexdigest()
            with self.db.connect() as conn:
                duplicate = conn.execute(
                    "SELECT id FROM sources WHERE checksum_sha256=?", (checksum,)
                ).fetchone()
            if duplicate:
                return {"duplicate": True, "source": self.get(duplicate[0])}
            source_id, timestamp = uuid4().hex, now()
            directory = self.settings.data_dir / "sources" / source_id
            directory.mkdir()
            raw = directory / f"original{extension}"
            temp.replace(raw)
            try:
                with self.db.connect() as conn:
                    conn.execute(
                        "INSERT INTO sources(id,type,title,original_filename,mime_type,"
                        "file_uri,file_size,"
                        "checksum_sha256,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                        (
                            source_id,
                            source_type,
                            Path(filename).stem,
                            filename,
                            mime_type,
                            str(raw.relative_to(self.settings.data_dir)),
                            size,
                            checksum,
                            timestamp,
                            timestamp,
                        ),
                    )
                self.attach(notebook_id, source_id)
                job = self.jobs.enqueue("source_ingest", source_id, {"source_id": source_id})
            except sqlite3.IntegrityError:
                # Another upload can commit the same checksum while this file is streaming.
                with self.db.connect() as conn:
                    duplicate = conn.execute(
                        "SELECT id FROM sources WHERE checksum_sha256=?", (checksum,)
                    ).fetchone()
                    conn.execute("DELETE FROM sources WHERE id=?", (source_id,))
                shutil.rmtree(directory, ignore_errors=True)
                if duplicate and duplicate[0] != source_id:
                    return {"duplicate": True, "source": self.get(duplicate[0])}
                raise AppError(
                    "SOURCE_IMPORT_FAILED", "The source could not be saved. Retry the upload."
                ) from None
            except Exception:
                with self.db.connect() as conn:
                    conn.execute("DELETE FROM sources WHERE id=?", (source_id,))
                shutil.rmtree(directory, ignore_errors=True)
                raise
            return {"duplicate": False, "source": self.get(source_id), "job": job}
        finally:
            temp.unlink(missing_ok=True)
            await file.close()

    def import_urls(self, notebook_id: str, urls: list[str], save_images=False) -> dict:
        self.notebooks.get(notebook_id)
        results = []
        for index, value in enumerate(urls):
            try:
                result = self.import_url(notebook_id, normalize_web_url(value.strip()), save_images)
                results.append({"index": index, **result})
            except AppError as error:
                results.append({"index": index, "error_code": error.code})
        return {"results": results}

    def import_url(self, notebook_id: str, url: str, save_images=False) -> dict:
        with self.db.connect() as conn:
            existing = conn.execute(
                "SELECT id FROM sources WHERE type='web' AND json_extract(metadata_json,'$.url')=?",
                (url,),
            ).fetchone()
        if existing:
            if save_images:
                self.queue_web_images(existing[0])
            return {"duplicate": True, "source": self.get(existing[0])}
        source_id, timestamp = uuid4().hex, now()
        directory = self.settings.data_dir / "sources" / source_id
        directory.mkdir()
        try:
            with self.db.connect() as conn:
                conn.execute(
                    "INSERT INTO sources(id,type,title,original_filename,mime_type,file_uri,"
                    "file_size,checksum_sha256,metadata_json,created_at,updated_at) "
                    "VALUES (?,'web',?,'webpage.html','text/html',?,0,?,?,?,?)",
                    (
                        source_id,
                        urlsplit(url).hostname,
                        str((directory / "original.html").relative_to(self.settings.data_dir)),
                        hashlib.sha256(("pending-web:" + url).encode()).hexdigest(),
                        json.dumps({"url": url, "save_images": save_images}),
                        timestamp,
                        timestamp,
                    ),
                )
            self.attach(notebook_id, source_id)
            job = self.jobs.enqueue("source_ingest", source_id, {"source_id": source_id})
            return {"duplicate": False, "source": self.get(source_id), "job": job}
        except sqlite3.IntegrityError:
            shutil.rmtree(directory, ignore_errors=True)
            with self.db.connect() as conn:
                existing = conn.execute(
                    "SELECT id FROM sources WHERE type='web' "
                    "AND json_extract(metadata_json,'$.url')=?",
                    (url,),
                ).fetchone()
            if existing:
                return {"duplicate": True, "source": self.get(existing[0])}
            raise AppError("SOURCE_IMPORT_FAILED", "The web source could not be saved.") from None
        except Exception:
            with self.db.connect() as conn:
                conn.execute("DELETE FROM sources WHERE id=?", (source_id,))
            shutil.rmtree(directory, ignore_errors=True)
            raise

    async def fetch_web_snapshot(self, row: dict, context: JobContext) -> None:
        path = self.settings.data_dir / row["file_uri"]
        manifest_path = path.with_name("web.json")
        # A saved snapshot is immutable. Parse/index retries never refetch the live page.
        if path.is_file() and manifest_path.is_file():
            manifest = json.loads(manifest_path.read_text())
            data = path.read_bytes()
            with self.db.connect() as conn:
                conn.execute(
                    "UPDATE sources SET file_size=?,checksum_sha256=?,metadata_json=? WHERE id=?",
                    (
                        len(data),
                        hashlib.sha256(manifest["url"].encode() + b"\0" + data).hexdigest(),
                        json.dumps(
                            {
                                **manifest,
                                "save_images": json.loads(row["metadata_json"]).get(
                                    "save_images", False
                                ),
                            }
                        ),
                        row["id"],
                    ),
                )
            return
        context.progress("fetching_web", 0.03)
        with self.db.connect() as conn:
            conn.execute("UPDATE sources SET status='fetching_web' WHERE id=?", (row["id"],))
        url = json.loads(row["metadata_json"])["url"]
        snapshot = await self.web_fetcher.fetch(url)
        manifest = {
            "url": url,
            "final_url": snapshot.final_url,
            "fetched_at": now(),
            "content_type": snapshot.content_type,
            "snapshot_sha256": hashlib.sha256(snapshot.data).hexdigest(),
        }
        metadata = {
            **manifest,
            "save_images": self.get(row["id"])["metadata"].get("save_images", False),
        }
        temporary = path.with_suffix(".tmp")
        temporary.write_bytes(snapshot.data)
        temporary.replace(path)
        temporary = manifest_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(manifest))
        temporary.replace(manifest_path)
        with self.db.connect() as conn:
            conn.execute(
                "UPDATE sources SET file_size=?,checksum_sha256=?,metadata_json=? WHERE id=?",
                (
                    len(snapshot.data),
                    hashlib.sha256(url.encode() + b"\0" + snapshot.data).hexdigest(),
                    json.dumps(metadata),
                    row["id"],
                ),
            )

    async def ingest(self, payload: dict, context: JobContext) -> dict:
        source_id = payload["source_id"]
        with self.db.connect() as conn:
            row = conn.execute("SELECT * FROM sources WHERE id=?", (source_id,)).fetchone()
        if not row:
            raise AppError("SOURCE_NOT_FOUND", "Original source unavailable.", 404)
        parser_version, parser = self.parsers[row["type"]]
        parsed = row["parser_version"] == parser_version and not (
            payload.get("recognize_images")
            or (row["type"] != "web" and json.loads(row["metadata_json"]).get("image_failures"))
        )
        result = {"source_id": source_id, "skipped": parsed}
        try:
            if not parsed:
                if row["type"] == "web":
                    await self.fetch_web_snapshot(dict(row), context)
                context.progress("parsing", 0.1)
                with self.db.connect() as conn:
                    conn.execute(
                        "UPDATE sources SET "
                        "status='parsing',error_code=NULL,error_message=NULL WHERE id=?",
                        (source_id,),
                    )
                args = (self.settings.data_dir / row["file_uri"], source_id)
                if row["type"] != "epub":
                    args += (Path(row["original_filename"]).stem,)
                document = await joined_thread(parser.parse, *args)
                if row["type"] == "web":
                    document.metadata["save_images"] = self.get(source_id)["metadata"].get(
                        "save_images", False
                    )
                if document.images and self.vision:
                    with self.db.connect() as conn:
                        conn.execute(
                            "UPDATE sources SET status='recognizing_images' WHERE id=?",
                            (source_id,),
                        )
                    await self.vision.enrich(dict(row), document, context)
                context.progress("normalizing", 0.4)
                self.persist_document(source_id, document, parser_version)
                if row["type"] == "web" and document.metadata["save_images"]:
                    self.queue_web_images(source_id)
                result["block_count"] = len(document.blocks)
                if not any(b.text.strip() for b in document.blocks):
                    raise AppError(
                        "SOURCE_VISION_FAILED"
                        if document.metadata.get("image_failures")
                        else "SOURCE_NO_TEXT",
                        "No usable text was recognized. "
                        "Configure a language model with image input and retry.",
                    )
            if self.indexer:
                result.update(await self.indexer.index(source_id, context))
        except Exception as exc:
            error = (
                exc
                if isinstance(exc, AppError)
                else AppError("SOURCE_PARSE_FAILED", "The source could not be parsed.")
            )
            with self.db.connect() as conn:
                conn.execute(
                    "UPDATE sources SET status='failed',error_code=?,error_message=?,updated_at=? "
                    "WHERE id=?",
                    (error.code, error.message, now(), source_id),
                )
            if error is exc:
                raise
            raise error from exc
        return result

    def queue_web_images(self, source_id):
        source = self.get(source_id)
        if source["type"] != "web":
            raise AppError("SOURCE_TYPE_UNSUPPORTED", "Only web sources use this image importer.")
        metadata = source["metadata"]
        if metadata.get("web_images_status") == "completed":
            return source["job"]
        metadata["save_images"] = True
        if metadata.get("web_images_status") != "completed":
            metadata["web_images_status"] = "queued"
        with self.db.connect() as conn:
            conn.execute(
                "UPDATE sources SET metadata_json=?,updated_at=? WHERE id=?",
                (json.dumps(metadata), now(), source_id),
            )
        # While HTML is pending, ingest will schedule images after the body is saved.
        if not source["parser_version"]:
            return source["job"]
        return self.jobs.enqueue("source_web_images", source_id, {"source_id": source_id})

    async def enrich_web_images(self, payload, context):
        try:
            return await self._enrich_web_images(payload, context)
        except Exception:
            source = self.get(payload["source_id"])
            metadata = {**source["metadata"], "web_images_status": "failed"}
            with self.db.connect() as conn:
                conn.execute(
                    "UPDATE sources SET metadata_json=?,updated_at=? WHERE id=?",
                    (json.dumps(metadata), now(), source["id"]),
                )
            raise

    async def _enrich_web_images(self, payload, context):
        source_id = payload["source_id"]
        source = self.get(source_id)
        path = self.settings.data_dir / "sources" / source_id / "original.html"
        document = await joined_thread(
            self.parsers["web"][1].parse, path, source_id, source["title"], True
        )
        published = {block["id"]: block for block in self.blocks(source_id)}
        # Adding images must not re-author existing article/citation facts, including
        # when an extractor upgrade would produce a different body from the snapshot.
        body_ids = {block.id for block in document.blocks}
        if body_ids != {
            identity for identity, block in published.items() if block["type"] != "image"
        } or any(
            block.text != published[block.id]["text"]
            or block.node_id != published[block.id]["node_id"]
            or block.type != published[block.id]["type"]
            or block.location != published[block.id]["location"]
            for block in document.blocks
        ):
            raise AppError(
                "SOURCE_PARSE_FAILED", "Image extraction did not match the saved article."
            )
        document.metadata["save_images"] = True
        document.metadata["web_images_version"] = WEB_IMAGES_VERSION
        candidates = list(document.images)
        ready = asyncio.Queue() if self.vision and candidates else None

        async def download_images():
            downloads = await self.web_images.download(
                source_id,
                document,
                context,
                source["metadata"].get("images", []),
                on_saved=(lambda index, image: ready.put_nowait((index, image))) if ready else None,
            )
            document.images = [
                image
                for image, info in zip(candidates, downloads, strict=True)
                if info["status"] == "saved"
            ]
            for image, info in zip(candidates, downloads, strict=True):
                if info["status"] == "skipped":
                    continue
                if info["status"] == "saved" and self.vision:
                    continue
                document.blocks.append(
                    DocumentBlock(
                        image.id,
                        image.node_id,
                        "image",
                        image.after_ordinal,
                        "",
                        image.location,
                        metadata={
                            "image_id": image.id,
                            "image_url": info.get("image_url"),
                            "original_image_url": info.get("original_image_url"),
                            "kind": image.kind,
                            "extraction": "vision",
                            "recognition_status": info["status"],
                            "error_code": info.get("error_code"),
                        },
                    )
                )
            return downloads

        if ready is not None:

            async def producer():
                downloads = await download_images()
                # Enough sentinels even if a settings save races the pool snapshot.
                for _ in range(min(20, len(candidates))):
                    ready.put_nowait(None)
                return downloads

            # The download deadline covers downloads only, while recognition drains
            # saved originals concurrently. Fatal errors/cancellation join both pools.
            async with asyncio.TaskGroup() as group:
                downloading = group.create_task(producer())
                await self.vision.enrich({"id": source_id}, document, context, ready=ready)
            downloads = downloading.result()
        else:
            downloads = await download_images()
            document.blocks.sort(key=lambda block: block.ordinal)
            for ordinal, block in enumerate(document.blocks):
                block.ordinal = ordinal
            document.metadata["images"] = []
        recognized = {info["id"]: info for info in document.metadata["images"]}
        images = [{**info, **recognized.get(info["id"], {})} for info in downloads]
        document.metadata["images"] = images
        document.metadata["image_failures"] = sum(
            i["status"] in ("failed", "saved") for i in images
        )
        document.metadata["web_images_status"] = (
            "partial" if document.metadata["image_failures"] else "completed"
        )
        for block in document.blocks:
            previous = published.get(block.id)
            if (
                block.type == "image"
                and previous
                and previous["metadata"].get("recognition_status") == "ready"
            ):
                block.text, block.metadata, block.location = (
                    previous["text"],
                    previous["metadata"],
                    previous["location"],
                )
        self.persist_document(source_id, document, WEB_PARSER_VERSION)
        result = {
            "source_id": source_id,
            "image_count": len(images),
            "image_failures": document.metadata["image_failures"],
        }
        if self.indexer:
            result.update(await self.indexer.index(source_id, context))
        return result

    def persist_document(self, source_id: str, document: Document, parser_version: str) -> None:
        node_rows = [
            (
                n.id,
                source_id,
                n.parent_id,
                n.type,
                n.title,
                n.depth,
                n.ordinal,
                n.start_page,
                n.end_page,
                json.dumps(n.metadata),
            )
            for n in document.nodes
        ]
        block_rows = [
            (
                b.id,
                source_id,
                b.node_id,
                b.type,
                b.ordinal,
                b.text,
                b.page_start,
                b.page_end,
                json.dumps(b.location),
                json.dumps(b.metadata),
            )
            for b in document.blocks
        ]
        with self.db.connect() as conn:
            existing_nodes = [
                tuple(r)
                for r in conn.execute(
                    "SELECT * FROM source_nodes WHERE source_id=? ORDER BY ordinal", (source_id,)
                )
            ]
            existing_blocks = [
                tuple(r)
                for r in conn.execute(
                    "SELECT * FROM content_blocks WHERE source_id=? ORDER BY ordinal", (source_id,)
                )
            ]
            if existing_nodes != node_rows or existing_blocks != block_rows:
                # Chunk links cascade when blocks change. Invalidate the entire old index
                # atomically rather than leaving vectors that no longer have provenance.
                conn.execute("DELETE FROM chunks WHERE source_id=?", (source_id,))
                conn.execute("DELETE FROM source_nodes WHERE source_id=?", (source_id,))
                conn.executemany("INSERT INTO source_nodes VALUES (?,?,?,?,?,?,?,?,?,?)", node_rows)
                conn.executemany(
                    "INSERT INTO content_blocks VALUES (?,?,?,?,?,?,?,?,?,?)", block_rows
                )
            conn.execute(
                "UPDATE sources SET title=?,status='parsed',parser_version=?,metadata_json=?,"
                "error_code=NULL,error_message=NULL,updated_at=? WHERE id=?",
                (
                    document.title,
                    parser_version,
                    json.dumps(document.metadata),
                    now(),
                    source_id,
                ),
            )

    def nodes(self, source_id: str) -> list[dict]:
        source = self.get(source_id)
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM source_nodes WHERE source_id=? ORDER BY ordinal", (source_id,)
            ).fetchall()
        nodes = [{**dict(row), "metadata": json.loads(row["metadata_json"])} for row in rows]
        if source["type"] != "epub":
            return nodes
        toc = source["metadata"].get("toc", [])
        missing = [
            entry
            for entry in toc
            if entry.get("fragment")
            and not any(
                n["metadata"].get("href") == entry["href"]
                and n["metadata"].get("element_id") == entry["fragment"]
                for n in nodes
            )
        ]
        if not missing:
            return nodes
        key = (source["checksum_sha256"], source["updated_at"])
        cached = self.toc_cache.get(source_id)
        if cached and cached[0] == key:
            return nodes + cached[1]
        sections = source["metadata"].get("toc_sections")
        if sections is None:
            with self.db.connect() as conn:
                path = conn.execute(
                    "SELECT file_uri FROM sources WHERE id=?", (source_id,)
                ).fetchone()[0]
            try:
                sections = self.parser.parse(self.settings.data_dir / path, source_id).metadata.get(
                    "toc_sections", []
                )
            except (AppError, OSError):
                return nodes
        with self.db.connect() as conn:
            available = {
                r[0]
                for r in conn.execute(
                    "SELECT id FROM content_blocks WHERE source_id=?", (source_id,)
                )
            }
        derived = []
        for entry in missing:
            section = next(
                (
                    s
                    for s in sections
                    if s["href"] == entry["href"] and s["fragment"] == entry["fragment"]
                ),
                None,
            )
            chapter = next(
                (
                    n
                    for n in nodes
                    if n["type"] == "chapter" and n["metadata"].get("href") == entry["href"]
                ),
                None,
            )
            if not section or not chapter:
                continue
            derived.append(
                {
                    "id": stable_id(source_id, f"toc:{entry['href']}#{entry['fragment']}"),
                    "source_id": source_id,
                    "parent_id": chapter["id"],
                    "type": "heading",
                    "title": entry["title"],
                    "depth": chapter["depth"] + max(1, entry["depth"]),
                    "ordinal": len(nodes) + len(derived),
                    "start_page": None,
                    "end_page": None,
                    "metadata": {
                        "href": entry["href"],
                        "element_id": entry["fragment"],
                        "section_block_ids": [b for b in section["block_ids"] if b in available],
                    },
                }
            )
        # Nested directory anchors form a real scope hierarchy, even when their
        # HTML targets were not headings in the original normalized fact layer.
        for node in derived:
            index = next(
                i
                for i, entry in enumerate(toc)
                if entry["href"] == node["metadata"]["href"]
                and entry.get("fragment") == node["metadata"]["element_id"]
            )
            parent_entry = next(
                (
                    entry
                    for entry in reversed(toc[:index])
                    if entry["href"] == toc[index]["href"] and entry["depth"] < toc[index]["depth"]
                ),
                None,
            )
            if parent_entry:
                parent = next(
                    (
                        n
                        for n in nodes + derived
                        if n["metadata"].get("href") == parent_entry["href"]
                        and (
                            n["metadata"].get("element_id") == parent_entry["fragment"]
                            if parent_entry["fragment"]
                            else n["type"] == "chapter"
                        )
                    ),
                    None,
                )
                if parent:
                    node["parent_id"] = parent["id"]
        self.toc_cache[source_id] = (key, derived)
        return nodes + derived

    def blocks(self, source_id: str, node_id: str | None = None) -> list[dict]:
        self.get(source_id)
        if node_id:
            section = next((n for n in self.nodes(source_id) if n["id"] == node_id), None)
            if section and "section_block_ids" in section["metadata"]:
                identities = set(section["metadata"]["section_block_ids"])
                return [b for b in self.blocks(source_id) if b["id"] in identities]
        with self.db.connect() as conn:
            if node_id:
                node = conn.execute(
                    "SELECT id FROM source_nodes WHERE id=? AND source_id=?", (node_id, source_id)
                ).fetchone()
                if not node:
                    raise AppError("NODE_NOT_FOUND", "This section is unavailable.", 404)
                rows = conn.execute(
                    "WITH RECURSIVE subtree(id) AS (SELECT ? UNION ALL "
                    "SELECT n.id FROM source_nodes n "
                    "JOIN subtree s ON n.parent_id=s.id) SELECT b.* FROM content_blocks b "
                    "JOIN subtree s ON b.node_id=s.id ORDER BY b.ordinal",
                    (node_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM content_blocks WHERE source_id=? ORDER BY ordinal", (source_id,)
                ).fetchall()
        return [
            {
                **dict(row),
                "location": json.loads(row["location_json"]),
                "metadata": json.loads(row["metadata_json"]),
            }
            for row in rows
        ]

    def retry(self, source_id: str) -> dict:
        self.get(source_id)
        return self.jobs.enqueue("source_ingest", source_id, {"source_id": source_id})

    def recognize_images(self, source_id):
        source = self.get(source_id)
        if source["type"] == "web":
            return self.queue_web_images(source_id)
        return self.jobs.enqueue(
            "source_ingest", source_id, {"source_id": source_id, "recognize_images": True}
        )

    def media_path(self, source_id, image_id):
        source = self.get(source_id)
        if image_id not in {i["id"] for i in source["metadata"].get("images", [])}:
            raise AppError("SOURCE_MEDIA_NOT_FOUND", "This source image is unavailable.", 404)
        path = self.settings.data_dir / "sources" / source_id / "media" / (image_id + ".png")
        if (
            not path.resolve().is_relative_to(self.settings.data_dir.resolve())
            or not path.is_file()
        ):
            raise AppError("SOURCE_MEDIA_NOT_FOUND", "This source image is unavailable.", 404)
        return path

    def original_media_path(self, source_id, image_id):
        import re

        source = self.get(source_id)
        image = next((i for i in source["metadata"].get("images", []) if i["id"] == image_id), {})
        name = image.get("original_file", "")
        path = self.settings.data_dir / "sources" / source_id / "media" / name
        if (
            not re.fullmatch(r"original-[a-f0-9]{64}\.(png|jpg|webp|gif|avif)", name)
            or not path.is_file()
            or not path.resolve().is_relative_to(self.settings.data_dir.resolve())
        ):
            raise AppError("SOURCE_MEDIA_NOT_FOUND", "This source image is unavailable.", 404)
        return path

    def reading(self, source_id: str, node_id: str | None = None) -> list[dict]:
        selected = self.blocks(source_id, node_id)
        with self.db.connect() as conn:
            source = conn.execute(
                "SELECT type,file_uri FROM sources WHERE id=?", (source_id,)
            ).fetchone()
        if source["type"] != "pdf":
            return raw_reading(selected)
        return pdf_reading(
            self.settings.data_dir / source["file_uri"], self.blocks(source_id), selected
        )

    def passages(self, source_id: str, hits: list[dict], node_ids=None) -> list[dict]:
        """Expand hits to bounded paragraphs without changing stored source facts."""
        blocks = self.blocks(source_id)
        identities = {hit["block_id"] for hit in hits}
        with self.db.connect() as conn:
            source = conn.execute(
                "SELECT type,file_uri FROM sources WHERE id=?", (source_id,)
            ).fetchone()
        if source["type"] == "pdf":
            pages = {block["page_start"] for block in blocks if block["id"] in identities}
            selected = [
                block
                for block in blocks
                if block["page_start"] in pages
                and (node_ids is None or block["node_id"] in node_ids or block["id"] in node_ids)
            ]
            reading = pdf_reading(self.settings.data_dir / source["file_uri"], blocks, selected)
            # Include only permitted pages/nodes. Expansion must not escape a
            # frozen question scope even when a PDF block spans several lines.
            passages = project_passages(reading, selected)
        else:
            passages = raw_passages(
                [
                    block
                    for block in blocks
                    if block["id"] in identities
                    and (
                        node_ids is None or block["node_id"] in node_ids or block["id"] in node_ids
                    )
                ]
            )
        return select_passages(passages, hits)

    def permanently_delete(self, source_id: str) -> None:
        self.get(source_id)
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            discard_source_caches(conn, source_id)
            conn.execute("DELETE FROM sources WHERE id=?", (source_id,))
