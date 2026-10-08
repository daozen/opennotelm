from pathlib import Path
from typing import Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse, JSONResponse

from .artifact_downloads import SavedArtifact
from .deck_diagnostics import attempt_row
from .deck_schemas import DeckTitleInput
from .diagnostics import STAGES, identity
from .error_codes import safe_error_code
from .mindmap_schemas import MindMapBatchInput, MindMapInput
from .pdf_export import download_filename

router = APIRouter(prefix="/api")


async def mindmap_write(mindmap_id: str, request: Request):
    notebook_id = request.app.state.mindmaps.record(mindmap_id)["notebook_id"]
    async with request.app.state.jobs.entity_lock("notebook:" + notebook_id):
        async with request.app.state.jobs.entity_lock(mindmap_id):
            yield


@router.get("/notebooks/{notebook_id}/mindmaps")
def list_maps(notebook_id: str, request: Request):
    return request.app.state.mindmaps.list(notebook_id)


@router.post("/notebooks/{notebook_id}/mindmaps", status_code=202)
async def create(notebook_id: str, data: MindMapInput, request: Request):
    async with request.app.state.jobs.entity_lock("notebook:" + notebook_id):
        return request.app.state.mindmaps.create(notebook_id, data)


@router.post("/notebooks/{notebook_id}/mindmaps/batch", status_code=202)
async def batch(notebook_id: str, data: MindMapBatchInput, request: Request):
    async with request.app.state.jobs.entity_lock("notebook:" + notebook_id):
        return request.app.state.mindmaps.create_batch(notebook_id, data)


@router.get("/mindmaps/{mindmap_id}")
def get_map(mindmap_id: str, request: Request):
    return request.app.state.mindmaps.get(mindmap_id)


@router.get("/mindmaps/{mindmap_id}/sources")
def sources(mindmap_id: str, request: Request):
    return request.app.state.mindmaps.sources_used(mindmap_id)


@router.patch("/mindmaps/{mindmap_id}", dependencies=[Depends(mindmap_write)])
async def rename(mindmap_id: str, data: DeckTitleInput, request: Request):
    return request.app.state.mindmaps.rename(mindmap_id, data.title)


@router.post("/mindmaps/{mindmap_id}/stop", dependencies=[Depends(mindmap_write)])
async def stop(mindmap_id: str, request: Request):
    return await request.app.state.mindmaps.pause(mindmap_id)


@router.post(
    "/mindmaps/{mindmap_id}/resume", status_code=202, dependencies=[Depends(mindmap_write)]
)
async def resume(mindmap_id: str, request: Request):
    return request.app.state.mindmaps.resume(mindmap_id)


@router.delete("/mindmaps/{mindmap_id}", status_code=204, dependencies=[Depends(mindmap_write)])
async def delete(mindmap_id: str, request: Request):
    await request.app.state.mindmaps.delete(mindmap_id)
    request.app.state.artifact_downloads.invalidate(kind="mindmap", identity=mindmap_id)
    request.app.state.files.drain()


@router.get("/mindmaps/{mindmap_id}/download", dependencies=[Depends(mindmap_write)])
async def download(
    mindmap_id: str, request: Request, format: Literal["markdown", "json"] = "markdown"
):
    from .errors import AppError

    service = request.app.state.mindmaps
    value = service.get(mindmap_id)
    if not value["tree"]:
        raise AppError("ARTIFACT_NOT_READY", "Complete this mind map before downloading.", 409)
    if format == "json":
        name = Path(download_filename(value["title"])).with_suffix(".json").name
        return JSONResponse(
            {
                "title": value["title"],
                "language": value["input"]["language"],
                "tree": value["tree"],
                "citations": value["citations"],
                "source_manifest": value["source_manifest"],
            },
            headers={
                "Content-Disposition": "attachment; filename*=UTF-8''" + quote(name, safe=""),
                "Cache-Control": "no-store",
            },
        )
    return FileResponse(
        service.file(mindmap_id),
        media_type="text/markdown; charset=utf-8",
        filename=service.download_name(mindmap_id),
        headers={"Cache-Control": "no-store"},
    )


class MindMapDownloadAdapter:
    def __init__(self, service):
        self.service = service

    def resolve(self, notebook_id, identity):
        from .errors import AppError

        value = self.service.get(identity)
        if value["notebook_id"] != notebook_id:
            raise AppError("ARTIFACT_NOT_FOUND", "A selected artifact is unavailable.", 404)
        if not value["download_available"]:
            raise AppError("ARTIFACT_NOT_READY", "Complete this mind map before downloading.", 409)
        return SavedArtifact(
            self.service.file(identity),
            self.service.download_name(identity),
            self.service.record(identity)["export"]["sha256"],
        )


@router.get("/mindmaps/{mindmap_id}/diagnostics")
def diagnostics(mindmap_id: str, request: Request):
    request.app.state.mindmaps.record(mindmap_id)
    with request.app.state.db.connect() as conn:
        jobs = [
            {
                "id": identity(r["id"]),
                "status": r["status"]
                if r["status"] in {"queued", "running", "completed", "failed", "cancelled"}
                else "unknown",
                "stage": r["stage"] if r["stage"] in STAGES else "unknown",
                "error_code": safe_error_code(r["error_code"]),
                "retry_count": r["retry_count"],
            }
            for r in conn.execute(
                "SELECT * FROM jobs WHERE entity_id=? ORDER BY rowid DESC LIMIT 100", (mindmap_id,)
            )
        ]
        attempts = [
            attempt_row(r)
            for r in conn.execute(
                (
                    "SELECT a.* FROM generation_attempts a JOIN jobs j ON j.id=a.job_id WHERE "
                    "j.entity_id=? ORDER BY a.id DESC LIMIT 500"
                ),
                (mindmap_id,),
            )
        ]
    return JSONResponse(
        {"report_version": 1, "mindmap_id": mindmap_id, "jobs": jobs, "attempts": attempts},
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": "attachment; filename=mindmap-diagnostics.json",
        },
    )
