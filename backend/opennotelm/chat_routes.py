from fastapi import APIRouter, Request

from .chat import ChatInput

router = APIRouter(prefix="/api")


@router.get("/notebooks/{notebook_id}/chat")
def get_chat(notebook_id: str, request: Request):
    return request.app.state.chat.messages(notebook_id)


@router.post("/notebooks/{notebook_id}/chat", status_code=202)
def send_chat(notebook_id: str, data: ChatInput, request: Request):
    return request.app.state.chat.send(notebook_id, data)


@router.get("/citations/{citation_id}")
def get_citation(citation_id: str, request: Request):
    if citation_id.startswith("preview:"):
        return request.app.state.transformations.citation(citation_id)
    return request.app.state.citations.get(citation_id)
