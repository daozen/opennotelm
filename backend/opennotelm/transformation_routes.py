from fastapi import APIRouter, Request, Response

from .transformations import TransformationInput

router = APIRouter(prefix="/api")


@router.post("/notebooks/{notebook_id}/transformations", status_code=202)
def create(notebook_id: str, data: TransformationInput, request: Request):
    return request.app.state.transformations.create(notebook_id, data)


@router.get("/transformations/{identity}")
def get(identity: str, request: Request):
    return request.app.state.transformations.get(identity)


@router.delete("/transformations/{identity}", status_code=204)
def discard(identity: str, request: Request):
    request.app.state.transformations.discard(identity)
    return Response(status_code=204)


@router.post("/transformations/{identity}/save", status_code=201)
def save(identity: str, request: Request):
    return request.app.state.transformations.save(identity)
