"""Lossless page images; native pages additionally keep their measured invisible text."""

import asyncio
import hashlib
import json
import re
import shutil
import unicodedata
from uuid import uuid4

from pypdf import PdfReader, PdfWriter
from pypdf.generic import ContentStream, DecodedStreamObject, NumberObject

from .errors import AppError
from .model_service import now
from .pdf_images import ENCODING_VERSION, raster_pdf
from .pdf_text import restore_source_unicode
from .telemetry import EventProperties

EXPORT_VERSION = "image-aligned-text-v2"
PAINT_PATH = {b"S", b"s", b"f", b"F", b"f*", b"B", b"B*", b"b", b"b*"}


def optimized_digest(legacy):
    return hashlib.sha256(f"{ENCODING_VERSION}:{legacy}".encode()).hexdigest()


def download_filename(title):
    name = re.sub(r'[\x00-\x1f\x7f/\\:*?"<>|]', "_", unicodedata.normalize("NFC", title)).strip(
        " ."
    )
    if name.lower().endswith(".pdf"):
        name = name[:-4].rstrip(" .")
    name = name or "Visual Deck"
    if re.fullmatch(r"(?i)(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?", name):
        name = "_" + name
    while len(name.encode("utf-8")) > 220:
        name = name[:-1]
    return name.rstrip(" .") + ".pdf"


def invisible_stream(stream, resources, reader, depth=0):
    resources = resources.get_object()
    if depth > 16:
        raise AppError("PDF_RENDER_INVALID", "The rendered page has unsupported nested graphics.")
    operations = []
    for operands, operator in stream.operations:
        if operator == b"BT":
            operations.extend([(operands, operator), ([NumberObject(3)], b"Tr")])
        elif operator == b"Tr":
            operations.append(([NumberObject(3)], b"Tr"))
        elif operator in PAINT_PATH:
            operations.append(([], b"n"))
        elif operator == b"Do":
            objects = resources["/XObject"] if "/XObject" in resources else {}
            target = objects.get(operands[0])
            if target and target.get_object().get("/Subtype") == "/Form":
                form = target.get_object()
                hidden = invisible_stream(
                    ContentStream(form, reader),
                    form.get("/Resources", resources),
                    reader,
                    depth + 1,
                )
                replacement = DecodedStreamObject()
                replacement.update(
                    {
                        k: v
                        for k, v in form.items()
                        if k not in {"/Filter", "/DecodeParms", "/Length"}
                    }
                )
                replacement.set_data(hidden.get_data())
                objects[operands[0]] = replacement
                operations.append((operands, operator))
        elif operator not in {b"sh", b"INLINE IMAGE"}:
            operations.append((operands, operator))
    stream.operations = operations
    return stream


def compact(text):
    return "".join(unicodedata.normalize("NFKC", text).split())


def assemble_pdf(title, pages, output):
    writer = PdfWriter()
    for index, page in enumerate(pages):
        native = PdfWriter(clone_from=page["pdf"])
        if len(native.pages) != 1 or list(native.pages[0].mediabox) != [0, 0, 1440, 810]:
            raise AppError(
                "PDF_RENDER_INVALID", "A page render has an unexpected size or page count."
            )
        text_page = native.pages[0]
        if page["text_layer"]:
            restore_source_unicode(text_page, page["text_layer"], native)
            contents = invisible_stream(text_page.get_contents(), text_page["/Resources"], native)
            text_page.replace_contents(contents)
        if (
            not page["text_layer"]
            and native.metadata
            and native.metadata.get("/Producer") == ENCODING_VERSION
        ):
            # Our whole-page PDF already contains exactly this raster, encoded once at rendering.
            added = writer.add_page(text_page)
        else:
            added = writer.add_page(raster_pdf(str(page["image"])).pages[0])
        if page["text_layer"]:
            added.merge_page(text_page)
        added.compress_content_streams()
        writer.add_outline_item(page["title"], index)
    writer.add_metadata({"/Title": title, "/Creator": "OpenNoteLM", "/Producer": ENCODING_VERSION})
    writer.write(output)
    check = PdfReader(output)
    if len(check.pages) != len(pages):
        raise AppError("PDF_PAGE_COUNT_INVALID", "The exported PDF has an incorrect page count.")
    for page, expected in zip(check.pages, pages, strict=True):
        text = compact(page.extract_text())
        if any(compact(item["text"]) not in text for item in expected["text_layer"]):
            raise AppError(
                "PDF_TEXT_INCOMPLETE",
                "Some page text could not be preserved in the PDF. Retry the page visual.",
            )


class PDFExportService:
    def __init__(self, db, jobs, settings):
        self.db, self.jobs, self.settings = db, jobs, settings
        self.telemetry = None
        jobs.handlers["deck_export"] = self.run

    def snapshot(self, deck_id, conn=None, *, optimized=False):
        if conn is None:
            with self.db.connect() as connection:
                return self.snapshot(deck_id, connection, optimized=optimized)
        # Display renames change HTTP filenames, not saved artifacts or their signatures.
        deck = conn.execute(
            "SELECT COALESCE(NULLIF(export_title,''),title) AS title FROM decks WHERE id=?",
            (deck_id,),
        ).fetchone()
        if not deck:
            raise AppError("DECK_NOT_FOUND", "This deck no longer exists.", 404)
        rows = conn.execute(
            "SELECT s.id,s.ordinal,s.revision,s.status,s.plan_json,s.spec_json,"
            "s.current_render_id,s.current_render_revision,"
            "r.image_uri,r.native_pdf_uri,r.text_layer_json FROM slides s "
            "LEFT JOIN slide_renders r "
            "ON r.id=s.current_render_id WHERE s.deck_id=? ORDER BY s.ordinal",
            (deck_id,),
        ).fetchall()
        if not rows or any(
            row["status"] != "rendered"
            or not row["image_uri"]
            or row["revision"] != row["current_render_revision"]
            for row in rows
        ):
            raise AppError(
                "DECK_NOT_RENDERED", "Finish or retry all page previews before exporting PDF.", 409
            )
        signature = {
            "version": EXPORT_VERSION,
            "title": deck["title"],
            "pages": [[r["id"], r["ordinal"], r["revision"], r["current_render_id"]] for r in rows],
        }
        digest = hashlib.sha256(json.dumps(signature, sort_keys=True).encode()).hexdigest()
        if optimized:
            digest = optimized_digest(digest)
        return deck["title"], rows, digest

    def public(self, row):
        return {
            "id": row["id"],
            "status": row["status"],
            "page_count": row["page_count"],
            "file_size": row["file_size"],
            "error_message": row["error_message"],
            "filename": self.download_name(row["id"]) if row["status"] == "ready" else None,
            "download_url": f"/api/pdf-exports/{row['id']}/file"
            if row["status"] == "ready"
            else None,
            "preview_url": f"/api/pdf-exports/{row['id']}/preview"
            if row["status"] == "ready"
            else None,
        }

    def download_name(self, export_id):
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT d.title FROM pdf_exports p JOIN decks d ON d.id=p.deck_id WHERE p.id=?",
                (export_id,),
            ).fetchone()
        if not row:
            raise AppError("PDF_NOT_FOUND", "This PDF no longer exists.", 404)
        return download_filename(row["title"])

    def current(self, deck_id):
        try:
            with self.db.connect() as conn:
                row = self.current_row(deck_id, conn)
        except AppError as error:
            if error.code == "DECK_NOT_RENDERED":
                return None
            raise
        return self.public(row) if row else None

    def current_row(self, deck_id, conn):
        legacy = self.snapshot(deck_id, conn)[2]
        optimized = optimized_digest(legacy)
        return conn.execute(
            "SELECT * FROM pdf_exports WHERE deck_id=? AND input_hash IN (?,?) "
            "ORDER BY CASE WHEN status='ready' AND input_hash=? THEN 0 "
            "WHEN status='ready' THEN 1 WHEN input_hash=? THEN 2 ELSE 3 END LIMIT 1",
            (deck_id, legacy, optimized, optimized, optimized),
        ).fetchone()

    def downloadable(self, deck_id, conn):
        try:
            row = self.current_row(deck_id, conn)
        except AppError as error:
            if error.code in ("DECK_NOT_RENDERED", "DECK_NOT_FOUND"):
                return False
            raise
        if not row or row["status"] != "ready" or not row["file_uri"]:
            return False
        path = (self.settings.data_dir / row["file_uri"]).resolve()
        return path.is_relative_to(self.settings.data_dir.resolve()) and path.is_file()

    def enqueue(self, deck_id):
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            self.snapshot(deck_id, conn)
            if conn.execute(
                "SELECT 1 FROM jobs WHERE entity_id=? AND status IN ('queued','running')",
                (deck_id,),
            ).fetchone():
                raise AppError("DECK_BUSY", "Wait for the current deck task to finish.", 409)
            job_id = self.jobs.enqueue_in_transaction(
                conn, "deck_export", deck_id, {"deck_id": deck_id, "optimize": True}
            )
        return self.jobs.get(job_id)

    async def run(self, payload, context):
        return await self.build(
            payload["deck_id"], context, optimize=payload.get("optimize", False)
        )

    async def build(self, deck_id, context, *, optimize=False):
        title, rows, digest = self.snapshot(deck_id, optimized=True)
        with self.db.connect() as conn:
            old = conn.execute(
                "SELECT * FROM pdf_exports WHERE deck_id=? AND input_hash=?", (deck_id, digest)
            ).fetchone()
            cached = old if optimize else self.current_row(deck_id, conn)
        if cached and cached["status"] == "ready":
            path = (self.settings.data_dir / cached["file_uri"]).resolve()
            if path.is_relative_to(self.settings.data_dir.resolve()) and path.is_file():
                if hashlib.sha256(path.read_bytes()).hexdigest() == cached["file_sha256"]:
                    with self.db.connect() as conn:
                        conn.execute("UPDATE decks SET status='ready' WHERE id=?", (deck_id,))
                    return self.public(cached)
        # An old encoding is immutable; an explicit re-export publishes a separate saved file.
        export_id = old["id"] if old else uuid4().hex
        directory = self.settings.data_dir / "exports" / export_id
        try:
            with self.db.connect() as conn:
                conn.execute(
                    "UPDATE decks SET status='exporting',updated_at=? WHERE id=?", (now(), deck_id)
                )
                conn.execute(
                    "INSERT INTO pdf_exports(id,deck_id,input_hash,status,created_at,updated_at) "
                    "VALUES (?,?,?,'generating',?,?) ON CONFLICT(deck_id,input_hash) DO UPDATE SET "
                    "status='generating',error_code=NULL,error_message=NULL,updated_at=excluded"
                    ".updated_at",
                    (export_id, deck_id, digest, now(), now()),
                )
            context.progress("exporting", 0.1)
            pages = []
            for row in rows:
                paths = [
                    (self.settings.data_dir / row[key]).resolve()
                    for key in ("image_uri", "native_pdf_uri")
                ]
                if any(
                    not p.is_relative_to(self.settings.data_dir.resolve()) or not p.is_file()
                    for p in paths
                ):
                    raise AppError(
                        "RENDER_NOT_FOUND",
                        "A rendered page file is missing. Retry that page visual.",
                        409,
                    )
                pages.append(
                    {
                        "image": paths[0],
                        "pdf": paths[1],
                        "title": next(
                            (
                                e["text"]
                                for e in json.loads(row["spec_json"])["content_elements"]
                                if e["type"] == "headline"
                            ),
                            json.loads(row["plan_json"])["title"],
                        ),
                        "text_layer": json.loads(row["text_layer_json"]),
                    }
                )
            directory.mkdir(parents=True, exist_ok=True)
            temporary, target = directory / "deck.tmp.pdf", directory / "deck.pdf"
            assembly = asyncio.create_task(asyncio.to_thread(assemble_pdf, title, pages, temporary))
            try:
                await asyncio.shield(assembly)
            except asyncio.CancelledError as cancellation:
                # A thread cannot be cancelled. Join it before a recovered job can use this path.
                try:
                    await assembly
                except Exception:
                    pass
                raise cancellation
            context.progress("exporting", 0.9)
            with self.db.connect() as conn:
                conn.execute("BEGIN IMMEDIATE")
                if self.snapshot(deck_id, conn, optimized=True)[2] != digest:
                    raise AppError(
                        "DECK_CHANGED", "The deck changed during export. Export it again.", 409
                    )
                temporary.replace(target)
                conn.execute(
                    "UPDATE pdf_exports SET status='ready',file_uri=?,page_count=?,file_size=?,"
                    "file_sha256=?,error_code=NULL,error_message=NULL,updated_at=? WHERE id=?",
                    (
                        str(target.relative_to(self.settings.data_dir)),
                        len(pages),
                        target.stat().st_size,
                        hashlib.sha256(target.read_bytes()).hexdigest(),
                        now(),
                        export_id,
                    ),
                )
                conn.execute(
                    "UPDATE decks SET status='ready',updated_at=? WHERE id=?", (now(), deck_id)
                )
            if self.telemetry:
                self.telemetry.capture("pdf_exported", EventProperties(slide_count=len(pages)))
            return self.current(deck_id)
        except asyncio.CancelledError:
            # The durable job resumes; unfinished files are never advertised as ready.
            raise
        except Exception as exc:
            error = (
                exc
                if isinstance(exc, AppError)
                else AppError(
                    "PDF_EXPORT_FAILED", "PDF export failed. Retry exporting the deck.", 502
                )
            )
            with self.db.connect() as conn:
                conn.execute(
                    "UPDATE pdf_exports SET status='failed',error_code=?,error_message=?,"
                    "updated_at=? WHERE id=?",
                    (error.code, error.message, now(), export_id),
                )
                conn.execute(
                    "UPDATE decks SET status='failed',updated_at=? WHERE id=?", (now(), deck_id)
                )
            shutil.rmtree(directory, ignore_errors=True)
            raise error from exc

    def file(self, export_id):
        with self.db.connect() as conn:
            row = conn.execute("SELECT * FROM pdf_exports WHERE id=?", (export_id,)).fetchone()
        if not row or row["status"] != "ready":
            raise AppError("PDF_NOT_FOUND", "This PDF is unavailable.", 404)
        legacy = self.snapshot(row["deck_id"])[2]
        if row["input_hash"] not in {legacy, optimized_digest(legacy)}:
            raise AppError(
                "PDF_OUTDATED", "The deck changed. Export the current version first.", 409
            )
        path = (self.settings.data_dir / row["file_uri"]).resolve()
        if not path.is_relative_to(self.settings.data_dir.resolve()) or not path.is_file():
            raise AppError("PDF_NOT_FOUND", "The PDF file is missing. Export it again.", 404)
        if hashlib.sha256(path.read_bytes()).hexdigest() != row["file_sha256"]:
            raise AppError("PDF_FILE_INVALID", "The PDF file is damaged. Export it again.", 409)
        return path
