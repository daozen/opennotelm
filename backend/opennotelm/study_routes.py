from pathlib import Path
from typing import Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse, JSONResponse

from .deck_diagnostics import attempt_row
from .deck_schemas import DeckTitleInput
from .diagnostics import STAGES, identity
from .error_codes import safe_error_code
from .errors import AppError
from .pdf_export import download_filename
from .study_schemas import StudyBatchInput, StudyInput, StudyResetInput, StudyResponseInput

Resource = Literal["quizzes", "flashcards"]


def service(request, resource):
    return getattr(request.app.state, resource)


def study_router(resource: Resource):
    router = APIRouter(prefix="/api")

    async def study_write(study_id: str, request: Request):
        notebook = service(request, resource).record(study_id)["notebook_id"]
        async with request.app.state.jobs.entity_lock("notebook:" + notebook):
            async with request.app.state.jobs.entity_lock(study_id):
                yield

    @router.get(f"/notebooks/{{notebook_id}}/{resource}")
    def list_studies(notebook_id: str, request: Request):
        return service(request, resource).list(notebook_id)

    @router.post(f"/notebooks/{{notebook_id}}/{resource}", status_code=202)
    async def create(notebook_id: str, data: StudyInput, request: Request):
        async with request.app.state.jobs.entity_lock("notebook:" + notebook_id):
            return service(request, resource).create(notebook_id, data)

    @router.post(f"/notebooks/{{notebook_id}}/{resource}/batch", status_code=202)
    async def batch(notebook_id: str, data: StudyBatchInput, request: Request):
        async with request.app.state.jobs.entity_lock("notebook:" + notebook_id):
            return service(request, resource).create_batch(notebook_id, data)

    @router.get(f"/{resource}/{{study_id}}")
    def get_study(study_id: str, request: Request):
        return service(request, resource).get(study_id)

    @router.get(f"/{resource}/{{study_id}}/sources")
    def sources(study_id: str, request: Request):
        return service(request, resource).sources_used(study_id)

    @router.patch(f"/{resource}/{{study_id}}", dependencies=[Depends(study_write)])
    async def rename(study_id: str, data: DeckTitleInput, request: Request):
        return service(request, resource).rename(study_id, data.title)

    @router.post(f"/{resource}/{{study_id}}/stop", dependencies=[Depends(study_write)])
    async def stop(study_id: str, request: Request):
        return await service(request, resource).pause(study_id)

    @router.post(
        f"/{resource}/{{study_id}}/resume", status_code=202, dependencies=[Depends(study_write)]
    )
    async def resume(study_id: str, request: Request):
        return service(request, resource).resume(study_id)

    @router.delete(
        f"/{resource}/{{study_id}}", status_code=204, dependencies=[Depends(study_write)]
    )
    async def delete(study_id: str, request: Request):
        value = service(request, resource)
        await value.delete(study_id)
        request.app.state.artifact_downloads.invalidate(kind=value.kind, identity=study_id)
        request.app.state.files.drain()

    @router.post(f"/{resource}/{{study_id}}/responses", dependencies=[Depends(study_write)])
    async def respond(study_id: str, data: StudyResponseInput, request: Request):
        return service(request, resource).respond(study_id, data)

    @router.post(f"/{resource}/{{study_id}}/reset", dependencies=[Depends(study_write)])
    async def reset(study_id: str, data: StudyResetInput, request: Request):
        return service(request, resource).respond(study_id, data, reset=True)

    @router.get(f"/{resource}/{{study_id}}/download", dependencies=[Depends(study_write)])
    async def download(
        study_id: str,
        request: Request,
        format: Literal["markdown", "json"] = "markdown",
    ):
        owner = service(request, resource)
        value = owner.get(study_id)
        if not value["download_available"]:
            raise AppError("ARTIFACT_NOT_READY", "Complete generation before downloading.", 409)
        if format == "json":
            name = Path(download_filename(value["title"])).with_suffix(".json").name
            return JSONResponse(
                {
                    "title": value["title"],
                    "language": value["input"]["language"],
                    "kind": owner.kind,
                    "content": owner.record(study_id)["tree"],
                    "citations": value["citations"],
                    "source_manifest": value["source_manifest"],
                },
                headers={
                    "Content-Disposition": "attachment; filename*=UTF-8''" + quote(name, safe=""),
                    "Cache-Control": "no-store",
                },
            )
        return FileResponse(
            owner.file(study_id),
            media_type="text/markdown; charset=utf-8",
            filename=owner.download_name(study_id),
            headers={"Cache-Control": "no-store"},
        )

    @router.get(f"/{resource}/{{study_id}}/diagnostics")
    def diagnostics(study_id: str, request: Request):
        owner = service(request, resource)
        owner.record(study_id)
        with request.app.state.db.connect() as conn:
            jobs = [
                {
                    "id": identity(r["id"]),
                    "status": r["status"],
                    "stage": r["stage"] if r["stage"] in STAGES else "unknown",
                    "error_code": safe_error_code(r["error_code"]),
                    "retry_count": r["retry_count"],
                }
                for r in conn.execute(
                    "SELECT * FROM jobs WHERE entity_id=? ORDER BY rowid DESC LIMIT 100",
                    (study_id,),
                )
            ]
            attempts = [
                attempt_row(r)
                for r in conn.execute(
                    "SELECT a.* FROM generation_attempts a JOIN jobs j ON j.id=a.job_id "
                    "WHERE j.entity_id=? ORDER BY a.id DESC LIMIT 500",
                    (study_id,),
                )
            ]
        return JSONResponse(
            {"report_version": 1, "artifact_id": study_id, "jobs": jobs, "attempts": attempts},
            headers={"Cache-Control": "no-store"},
        )

    return router


router = APIRouter()
router.include_router(study_router("quizzes"))
router.include_router(study_router("flashcards"))
