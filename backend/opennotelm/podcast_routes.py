from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse, JSONResponse

from .deck_diagnostics import attempt_row
from .diagnostics import STAGES, identity
from .error_codes import safe_error_code
from .pdf_export import download_filename
from .podcast_schemas import PodcastBatchInput, PodcastEdit, PodcastInput, PodcastTitleInput

router = APIRouter(prefix="/api")


async def podcast_write(podcast_id: str, request: Request):
    notebook_id = request.app.state.podcasts.record(podcast_id)["notebook_id"]
    async with request.app.state.jobs.entity_lock("notebook:" + notebook_id):
        async with request.app.state.jobs.entity_lock(podcast_id):
            yield


@router.get("/notebooks/{notebook_id}/podcasts")
def list_podcasts(notebook_id: str, request: Request):
    return request.app.state.podcasts.list(notebook_id)


@router.post("/notebooks/{notebook_id}/podcasts", status_code=202)
async def create_podcast(notebook_id: str, data: PodcastInput, request: Request):
    async with request.app.state.jobs.entity_lock("notebook:" + notebook_id):
        return request.app.state.podcasts.create(notebook_id, data)


@router.post("/notebooks/{notebook_id}/podcasts/batch", status_code=202)
async def create_batch(notebook_id: str, data: PodcastBatchInput, request: Request):
    async with request.app.state.jobs.entity_lock("notebook:" + notebook_id):
        return request.app.state.podcasts.create_batch(notebook_id, data)


@router.get("/podcasts/{podcast_id}")
def get_podcast(podcast_id: str, request: Request):
    return request.app.state.podcasts.get(podcast_id)


@router.get("/podcasts/{podcast_id}/sources")
def podcast_sources(podcast_id: str, request: Request):
    return request.app.state.podcasts.sources_used(podcast_id)


@router.patch("/podcasts/{podcast_id}", dependencies=[Depends(podcast_write)])
async def rename(podcast_id: str, data: PodcastTitleInput, request: Request):
    return request.app.state.podcasts.rename(podcast_id, data.title)


@router.post("/podcasts/{podcast_id}/stop", dependencies=[Depends(podcast_write)])
async def stop(podcast_id: str, request: Request):
    return await request.app.state.podcasts.pause(podcast_id)


@router.post(
    "/podcasts/{podcast_id}/resume", status_code=202, dependencies=[Depends(podcast_write)]
)
async def resume(podcast_id: str, request: Request):
    return request.app.state.podcasts.resume(podcast_id)


@router.delete("/podcasts/{podcast_id}", status_code=204, dependencies=[Depends(podcast_write)])
async def delete(podcast_id: str, request: Request):
    await request.app.state.podcasts.delete(podcast_id)
    request.app.state.artifact_downloads.invalidate(kind="podcast", identity=podcast_id)
    request.app.state.files.drain()


@router.patch("/podcasts/{podcast_id}/segments/{segment_id}", dependencies=[Depends(podcast_write)])
async def edit(podcast_id: str, segment_id: str, data: PodcastEdit, request: Request):
    return request.app.state.podcasts.edit(podcast_id, segment_id, data)


@router.api_route(
    "/podcasts/{podcast_id}/audio", methods=["GET", "HEAD"], dependencies=[Depends(podcast_write)]
)
async def audio(podcast_id: str, request: Request, download: bool = False):
    service = request.app.state.podcasts
    return FileResponse(
        service.file(podcast_id),
        media_type="audio/mpeg",
        filename=service.download_name(podcast_id),
        content_disposition_type="attachment" if download else "inline",
        headers={"Cache-Control": "private, no-cache"},
    )


@router.get("/podcasts/{podcast_id}/transcript")
def transcript(podcast_id: str, request: Request):
    episode = request.app.state.podcasts.get(podcast_id)
    filename = Path(download_filename(episode["title"])).with_suffix(".json").name
    # Text stays explicit and user-controlled; operational diagnostics never include it.
    return JSONResponse(
        {
            "title": episode["title"],
            "language": episode["input"]["language"],
            "segments": episode["segments"],
        },
        headers={
            "Content-Disposition": "attachment; filename*=UTF-8''" + quote(filename, safe=""),
            "Cache-Control": "no-store",
        },
    )


@router.get("/podcasts/{podcast_id}/diagnostics")
def diagnostics(podcast_id: str, request: Request):
    request.app.state.podcasts.record(podcast_id)
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
                "SELECT * FROM jobs WHERE entity_id=? ORDER BY rowid DESC LIMIT 100", (podcast_id,)
            )
        ]
        attempts = [
            attempt_row(r)
            for r in conn.execute(
                (
                    "SELECT a.* FROM generation_attempts a JOIN jobs j ON j.id=a.job_id WHERE "
                    "j.entity_id=? ORDER BY a.id DESC LIMIT 500"
                ),
                (podcast_id,),
            )
        ]
    return JSONResponse(
        {"report_version": 1, "podcast_id": podcast_id, "jobs": jobs, "attempts": attempts},
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": "attachment; filename=podcast-diagnostics.json",
        },
    )
