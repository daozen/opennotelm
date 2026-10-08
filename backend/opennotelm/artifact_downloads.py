"""Temporary, bounded download bundles; adapters supply immutable saved files."""

import asyncio
import hashlib
import tempfile
import time
import unicodedata
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from uuid import uuid4
from zipfile import ZIP_STORED, ZipFile

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .concurrency import joined_thread
from .errors import AppError
from .pdf_export import download_filename

MAX_BUNDLE_BYTES = 512 * 1024 * 1024
MAX_CACHE_BYTES = 2 * MAX_BUNDLE_BYTES
BUNDLE_TTL = 30 * 60


class ArtifactRef(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["deck", "podcast", "mindmap"]
    id: str = Field(pattern=r"^[a-f0-9]{32}$")


class ArtifactDownloadInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[ArtifactRef] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def unique(self):
        if len({(item.kind, item.id) for item in self.items}) != len(self.items):
            raise ValueError("Select each artifact once.")
        return self


@dataclass
class SavedArtifact:
    path: Path
    filename: str
    sha256: str


class DeckDownloadAdapter:
    def __init__(self, db, exports, settings):
        self.db, self.exports, self.settings = db, exports, settings

    def resolve(self, notebook_id, identity):
        with self.db.connect() as conn:
            deck = conn.execute(
                "SELECT title FROM decks WHERE id=? AND notebook_id=?", (identity, notebook_id)
            ).fetchone()
            busy = conn.execute(
                "SELECT 1 FROM jobs WHERE entity_id=? AND status IN ('queued','running')",
                (identity,),
            ).fetchone()
        if not deck:
            raise AppError("ARTIFACT_NOT_FOUND", "A selected artifact is unavailable.", 404)
        current = self.exports.current(identity)
        if busy or not current or current["status"] != "ready":
            raise AppError(
                "ARTIFACT_NOT_READY", "A selected artifact has no current saved file.", 409
            )
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT file_uri,file_sha256 FROM pdf_exports WHERE id=?", (current["id"],)
            ).fetchone()
        if not row or not row["file_uri"]:
            raise AppError("PDF_NOT_FOUND", "The PDF file is missing. Export it again.", 404)
        path = (self.settings.data_dir / row["file_uri"]).resolve()
        if not path.is_relative_to(self.settings.data_dir.resolve()) or not path.is_file():
            raise AppError("PDF_NOT_FOUND", "The PDF file is missing. Export it again.", 404)
        return SavedArtifact(path, download_filename(deck["title"]), row["file_sha256"])


class PodcastDownloadAdapter:
    def __init__(self, podcasts):
        self.podcasts = podcasts

    def resolve(self, notebook_id, identity):
        episode = self.podcasts.get(identity)
        if episode["notebook_id"] != notebook_id:
            raise AppError("ARTIFACT_NOT_FOUND", "A selected artifact is unavailable.", 404)
        if not episode["download_available"]:
            raise AppError("ARTIFACT_NOT_READY", "Generate current audio before downloading.", 409)
        saved = self.podcasts.record(identity)["audio"]
        return SavedArtifact(
            self.podcasts.file(identity), self.podcasts.download_name(identity), saved["sha256"]
        )


def write_bundle(files, output):
    used, total = set(), 0
    with ZipFile(output, "w", compression=ZIP_STORED) as archive:
        for saved in files:
            filename = saved.filename
            stem, suffix = Path(filename).stem, Path(filename).suffix
            number = 2
            while unicodedata.normalize("NFKC", filename).casefold() in used:
                filename = f"{stem} ({number}){suffix}"
                number += 1
            used.add(unicodedata.normalize("NFKC", filename).casefold())
            digest = hashlib.sha256()
            with saved.path.open("rb") as source, archive.open(filename, "w") as target:
                while chunk := source.read(1024 * 1024):
                    total += len(chunk)
                    if total > MAX_BUNDLE_BYTES:
                        raise AppError(
                            "DOWNLOAD_TOO_LARGE", "Select fewer files per download.", 413
                        )
                    digest.update(chunk)
                    target.write(chunk)
            if digest.hexdigest() != saved.sha256:
                raise AppError("PDF_FILE_INVALID", "A saved file is damaged. Export it again.", 409)


class ArtifactDownloadService:
    def __init__(self, notebooks, jobs, adapters):
        self.notebooks, self.jobs, self.adapters = notebooks, jobs, adapters
        self.directory = tempfile.TemporaryDirectory(prefix="opennotelm-artifact-download-")
        self.entries = {}
        self.slots = asyncio.Semaphore(2)
        self.timer = asyncio.get_running_loop().call_later(60, self.reap)

    def reap(self):
        for token, entry in list(self.entries.items()):
            if entry["expires"] <= time.monotonic() and not entry["readers"]:
                self.remove(token)
        self.timer = asyncio.get_running_loop().call_later(60, self.reap)

    def remove(self, token):
        entry = self.entries.pop(token, None)
        if entry:
            entry["path"].unlink(missing_ok=True)

    def make_room(self, size):
        # Consecutive batches should not wait 30 minutes for old downloaded ZIPs.
        # Active transfers remain protected; older idle links can be prepared again.
        def full():
            return len(self.entries) >= 32 or (
                sum(entry["size"] for entry in self.entries.values()) + size > MAX_CACHE_BYTES
            )

        for token, entry in sorted(self.entries.items(), key=lambda item: item[1]["expires"]):
            if not full():
                break
            if not entry["readers"]:
                self.remove(token)
        if full():
            raise AppError("DOWNLOAD_CACHE_FULL", "Download storage is busy. Try later.", 429)

    def invalidate(self, *, notebook_id=None, kind=None, identity=None):
        for token, entry in list(self.entries.items()):
            if entry["notebook_id"] == notebook_id or any(
                item.kind == kind and item.id == identity for item in entry["items"]
            ):
                self.remove(token)

    @asynccontextmanager
    async def protect(self, notebook_id, items):
        async with AsyncExitStack() as stack:
            await stack.enter_async_context(self.jobs.entity_lock("notebook:" + notebook_id))
            for identity in sorted({item.id for item in items}):
                await stack.enter_async_context(self.jobs.entity_lock(identity))
            self.notebooks.get(notebook_id)
            yield

    async def prepare(self, notebook_id, items):
        async with self.slots, self.protect(notebook_id, items):
            files = await joined_thread(
                lambda: [self.adapters[item.kind].resolve(notebook_id, item.id) for item in items]
            )
            if sum(saved.path.stat().st_size for saved in files) > MAX_BUNDLE_BYTES:
                raise AppError("DOWNLOAD_TOO_LARGE", "Select fewer files per download.", 413)
            token = uuid4().hex
            path = Path(self.directory.name) / (token + ".zip")
            try:
                await joined_thread(write_bundle, files, path)
                size = path.stat().st_size
                if size > MAX_BUNDLE_BYTES:
                    raise AppError("DOWNLOAD_TOO_LARGE", "Select fewer files per download.", 413)
                self.make_room(size)
                filename = download_filename(self.notebooks.get(notebook_id)["title"])[:-4] + ".zip"
                self.entries[token] = {
                    "path": path,
                    "filename": filename,
                    "size": size,
                    "items": items,
                    "notebook_id": notebook_id,
                    "expires": time.monotonic() + BUNDLE_TTL,
                    "readers": 0,
                }
                return {
                    "download_url": f"/api/artifact-downloads/{token}/file",
                    "filename": filename,
                }
            except BaseException:
                path.unlink(missing_ok=True)
                raise

    def get(self, token):
        entry = self.entries.get(token)
        if not entry or entry["expires"] <= time.monotonic():
            raise AppError("DOWNLOAD_EXPIRED", "Prepare the download again.", 404)
        return entry

    def close(self):
        self.timer.cancel()
        self.entries.clear()
        self.directory.cleanup()


class BundleResponse(FileResponse):
    def __init__(self, service, token):
        self.service, self.token = service, token
        entry = service.get(token)
        super().__init__(
            entry["path"],
            filename=entry["filename"],
            media_type="application/zip",
            headers={"Cache-Control": "no-store"},
        )

    async def __call__(self, scope, receive, send):
        entry = self.service.get(self.token)
        async with self.service.protect(entry["notebook_id"], entry["items"]):
            entry = self.service.get(self.token)
            entry["readers"] += 1
            try:
                # Keep file ownership until bytes have actually been sent, including
                # servers that offer deferred pathsend outside the response lifetime.
                scope = {
                    **scope,
                    "extensions": {
                        key: value
                        for key, value in scope.get("extensions", {}).items()
                        if key != "http.response.pathsend"
                    },
                }
                await super().__call__(scope, receive, send)
            finally:
                entry["readers"] -= 1


router = APIRouter(prefix="/api")


@router.post("/notebooks/{notebook_id}/artifacts/download")
async def prepare_download(notebook_id: str, data: ArtifactDownloadInput, request: Request):
    return await request.app.state.artifact_downloads.prepare(notebook_id, data.items)


@router.get("/artifact-downloads/{token}/file")
async def download_bundle(token: str, request: Request):
    return BundleResponse(request.app.state.artifact_downloads, token)
