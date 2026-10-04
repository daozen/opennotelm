from fastapi import APIRouter, Request

from .knowledge import KnowledgeEdit, KnowledgeInput, SaveMessage

router = APIRouter(prefix="/api")


@router.get("/notebooks/{notebook_id}/knowledge")
def list_pages(notebook_id: str, request: Request):
    return request.app.state.knowledge.list(notebook_id)


@router.post("/notebooks/{notebook_id}/knowledge", status_code=202)
def create_page(notebook_id: str, data: KnowledgeInput, request: Request):
    return request.app.state.knowledge.create(notebook_id, data)


@router.post("/notebooks/{notebook_id}/knowledge/from-message", status_code=201)
def save_message(notebook_id: str, data: SaveMessage, request: Request):
    return request.app.state.knowledge.save_message(notebook_id, data)


@router.get("/knowledge/{page_id}")
def get_page(page_id: str, request: Request):
    return request.app.state.knowledge.get(page_id)


@router.patch("/knowledge/{page_id}")
def edit_page(page_id: str, data: KnowledgeEdit, request: Request):
    return request.app.state.knowledge.edit(page_id, data)


@router.post("/knowledge/{page_id}/update", status_code=202)
def update_page(page_id: str, data: KnowledgeInput, request: Request):
    return request.app.state.knowledge.enqueue_update(page_id, data)
