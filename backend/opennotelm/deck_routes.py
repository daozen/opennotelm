from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse, JSONResponse

from .deck_diagnostics import deck_report
from .deck_schemas import DeckBatchInput, DeckInput, DeckTitleInput
from .revision_schemas import DeleteSlideInput, EditTextInput, OrderInput, RevisionInput

router = APIRouter(prefix="/api")


async def deck_write(deck_id: str, request: Request):
    # Keep pause/resume/delete and edits serialized until cancelled work has unwound.
    async with request.app.state.jobs.entity_lock(deck_id):
        yield


@router.get("/notebooks/{notebook_id}/decks")
def list_decks(notebook_id: str, request: Request):
    return request.app.state.decks.list(notebook_id)


@router.post("/notebooks/{notebook_id}/decks", status_code=202)
def create_deck(notebook_id: str, data: DeckInput, request: Request):
    return request.app.state.decks.create(notebook_id, data)


@router.post("/notebooks/{notebook_id}/decks/batch", status_code=202)
def create_deck_batch(notebook_id: str, data: DeckBatchInput, request: Request):
    return request.app.state.decks.create_batch(notebook_id, data)


@router.get("/decks/{deck_id}")
def get_deck(deck_id: str, request: Request):
    return request.app.state.decks.get(deck_id)


@router.get("/decks/{deck_id}/sources")
def deck_sources(deck_id: str, request: Request):
    return request.app.state.decks.sources_used(deck_id)


@router.patch("/decks/{deck_id}", dependencies=[Depends(deck_write)])
async def rename_deck(deck_id: str, data: DeckTitleInput, request: Request):
    return request.app.state.decks.rename(deck_id, data.title)


@router.get("/decks/{deck_id}/diagnostics")
def deck_diagnostics(deck_id: str, request: Request, download: bool = False):
    headers = {"Cache-Control": "no-store"}
    if download:
        headers["Content-Disposition"] = 'attachment; filename="deck-diagnostics.json"'
    return JSONResponse(deck_report(request.app, deck_id), headers=headers)


@router.post("/decks/{deck_id}/stop", dependencies=[Depends(deck_write)])
async def stop_deck(deck_id: str, request: Request):
    return await request.app.state.decks.pause(deck_id)


@router.post("/decks/{deck_id}/resume", status_code=202, dependencies=[Depends(deck_write)])
async def resume_deck(deck_id: str, request: Request):
    return request.app.state.decks.resume(deck_id)


@router.delete("/decks/{deck_id}", status_code=204, dependencies=[Depends(deck_write)])
async def delete_deck(deck_id: str, request: Request):
    await request.app.state.decks.delete(deck_id)
    request.app.state.artifact_downloads.invalidate(kind="deck", identity=deck_id)
    request.app.state.files.drain()


@router.post("/decks/{deck_id}/retry", status_code=202, dependencies=[Depends(deck_write)])
async def retry_deck(deck_id: str, request: Request):
    return request.app.state.decks.retry(deck_id)


@router.post("/decks/{deck_id}/generated-copy", status_code=202, dependencies=[Depends(deck_write)])
async def generated_copy(
    deck_id: str, request: Request, rewrite_content: bool = False, restyle: bool | None = None
):
    return request.app.state.decks.generated_copy(
        deck_id, rewrite_content=rewrite_content, restyle=restyle
    )


@router.post(
    "/decks/{deck_id}/slides/{slide_id}/retry", status_code=202, dependencies=[Depends(deck_write)]
)
async def retry_slide(deck_id: str, slide_id: str, request: Request):
    return request.app.state.decks.retry_slide(deck_id, slide_id)


@router.post(
    "/decks/{deck_id}/slides/{slide_id}/without-image",
    status_code=202,
    dependencies=[Depends(deck_write)],
)
async def skip_slide_image(deck_id: str, slide_id: str, request: Request):
    return request.app.state.decks.retry_slide(deck_id, slide_id, without_image=True)


@router.post("/decks/{deck_id}/export", status_code=202, dependencies=[Depends(deck_write)])
async def export_pdf(deck_id: str, request: Request):
    return request.app.state.pdf_exports.enqueue(deck_id)


@router.get("/pdf-exports/{export_id}/file")
def download_pdf(export_id: str, request: Request):
    path = request.app.state.pdf_exports.file(export_id)
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=request.app.state.pdf_exports.download_name(export_id),
    )


@router.get("/pdf-exports/{export_id}/preview")
def preview_pdf(export_id: str, request: Request):
    return FileResponse(
        request.app.state.pdf_exports.file(export_id),
        media_type="application/pdf",
        filename=request.app.state.pdf_exports.download_name(export_id),
        content_disposition_type="inline",
    )


@router.post(
    "/decks/{deck_id}/slides/{slide_id}/revise", status_code=202, dependencies=[Depends(deck_write)]
)
async def revise_slide(deck_id: str, slide_id: str, data: RevisionInput, request: Request):
    return request.app.state.revisions.create(deck_id, slide_id, data)


@router.patch(
    "/decks/{deck_id}/slides/{slide_id}/text", status_code=202, dependencies=[Depends(deck_write)]
)
async def edit_slide_text(deck_id: str, slide_id: str, data: EditTextInput, request: Request):
    return request.app.state.revisions.edit(deck_id, slide_id, data)


@router.put("/decks/{deck_id}/order", dependencies=[Depends(deck_write)])
async def reorder_slides(deck_id: str, data: OrderInput, request: Request):
    return request.app.state.revisions.reorder(deck_id, data)


@router.delete("/decks/{deck_id}/slides/{slide_id}", dependencies=[Depends(deck_write)])
async def delete_slide(deck_id: str, slide_id: str, data: DeleteSlideInput, request: Request):
    result = request.app.state.revisions.delete(deck_id, slide_id, data)
    request.app.state.files.drain()
    return result
