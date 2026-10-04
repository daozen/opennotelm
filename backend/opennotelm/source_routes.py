import asyncio

from fastapi import APIRouter, Request, Response, UploadFile
from fastapi.responses import FileResponse
from pydantic import Field

from .schemas import StrictModel

router = APIRouter(prefix="/api")


class EnabledInput(StrictModel):
    enabled: bool


class WebImportInput(StrictModel):
    urls: list[str] = Field(min_length=1, max_length=50)
    save_images: bool = False


@router.get("/notebooks/{notebook_id}/sources")
def list_sources(notebook_id: str, request: Request):
    return request.app.state.sources.list(notebook_id)


@router.post("/notebooks/{notebook_id}/sources/upload", status_code=202)
async def upload_source(notebook_id: str, file: UploadFile, request: Request):
    return await request.app.state.sources.upload(notebook_id, file)


@router.post("/notebooks/{notebook_id}/sources/urls", status_code=202)
def import_web_sources(notebook_id: str, data: WebImportInput, request: Request):
    return request.app.state.sources.import_urls(notebook_id, data.urls, data.save_images)


@router.get("/sources/{source_id}/media/{image_id}/original")
def original_source_image(source_id: str, image_id: str, request: Request):
    path = request.app.state.sources.original_media_path(source_id, image_id)
    return FileResponse(path, media_type="application/octet-stream", filename=path.name)


@router.post("/notebooks/{notebook_id}/sources/{source_id}")
def attach_source(notebook_id: str, source_id: str, request: Request):
    return request.app.state.sources.attach(notebook_id, source_id)


@router.patch("/notebooks/{notebook_id}/sources/{source_id}")
def enable_source(notebook_id: str, source_id: str, data: EnabledInput, request: Request):
    return request.app.state.sources.set_enabled(notebook_id, source_id, data.enabled)


@router.delete("/notebooks/{notebook_id}/sources/{source_id}", status_code=204)
def detach_source(notebook_id: str, source_id: str, request: Request):
    request.app.state.sources.detach(notebook_id, source_id)
    return Response(status_code=204)


@router.get("/sources/{source_id}")
def get_source(source_id: str, request: Request):
    return request.app.state.sources.get(source_id)


@router.get("/sources/{source_id}/nodes")
def get_nodes(source_id: str, request: Request):
    return request.app.state.sources.nodes(source_id)


@router.get("/sources/{source_id}/media/{image_id}")
def source_image(source_id: str, image_id: str, request: Request):
    return FileResponse(
        request.app.state.sources.media_path(source_id, image_id), media_type="image/png"
    )


@router.post("/sources/{source_id}/recognize-images", status_code=202)
def recognize_images(source_id: str, request: Request):
    return request.app.state.sources.recognize_images(source_id)


@router.get("/sources/{source_id}/blocks")
def get_blocks(source_id: str, request: Request, node_id: str | None = None):
    return request.app.state.sources.blocks(source_id, node_id)


@router.post("/sources/{source_id}/retry", status_code=202)
def retry_source(source_id: str, request: Request):
    return request.app.state.sources.retry(source_id)


@router.get("/sources/{source_id}/reading")
async def reading(source_id: str, request: Request, node_id: str | None = None):
    return await asyncio.to_thread(request.app.state.sources.reading, source_id, node_id)


@router.delete("/sources/{source_id}", status_code=204)
def delete_source(source_id: str, request: Request):
    request.app.state.sources.permanently_delete(source_id)
    request.app.state.files.drain()
    return Response(status_code=204)


@router.get("/jobs/{job_id}")
def get_job(job_id: str, request: Request):
    return request.app.state.jobs.get(job_id)


@router.post("/jobs/{job_id}/retry", status_code=202)
async def retry_job(job_id: str, request: Request):
    jobs = request.app.state.jobs
    job = jobs.get(job_id)
    async with jobs.entity_lock(job["entity_id"]):
        return jobs.retry(job_id)
