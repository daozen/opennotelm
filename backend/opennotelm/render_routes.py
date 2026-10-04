from typing import Literal

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse

router = APIRouter(prefix="/api")


@router.get("/renders/{render_id}/{kind}")
def render_file(render_id: str, kind: Literal["image", "thumbnail"], request: Request):
    return FileResponse(request.app.state.composition.file(render_id, kind), media_type="image/png")
