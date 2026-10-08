import json
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from . import __version__
from .artifact_downloads import ArtifactDownloadService, DeckDownloadAdapter, PodcastDownloadAdapter
from .artifact_downloads import router as artifact_download_router
from .artifact_instructions import router as artifact_instruction_router
from .assets import AssetService
from .chat import ChatService
from .chat_routes import router as chat_router
from .citations import CitationService
from .composition import CompositionService
from .config import Settings
from .db import Database
from .deck_routes import router as deck_router
from .decks import DeckService
from .diagnostics import diagnostic_report
from .errors import AppError
from .gateway import ModelGateway
from .index_rebuild import IndexRebuildService
from .instance import instance_lock
from .job_events import configure_logging
from .jobs import JobService
from .knowledge import KnowledgeService
from .knowledge_routes import router as knowledge_router
from .maintenance import FileMaintenance
from .mindmap_routes import MindMapDownloadAdapter
from .mindmap_routes import router as mindmap_router
from .mindmaps import MindMapService
from .model_service import ModelService
from .notebooks import NotebookService
from .pdf_export import PDFExportService
from .podcast_routes import router as podcast_router
from .podcasts import PodcastService
from .render_routes import router as render_router
from .retrieval import RetrievalService
from .revisions import RevisionService
from .schemas import (
    ContentGenerationSettingsInput,
    ImageGenerationSettingsInput,
    ImageRecognitionSettingsInput,
    IndexRebuildInput,
    ModelRequestConcurrencyInput,
    ModelTestInput,
    NotebookInput,
    PreferencesInput,
    SpeechGenerationSettingsInput,
    TaskConcurrencyInput,
)
from .secrets import SecretStore
from .source_routes import router as source_router
from .source_service import SourceService
from .source_vision import SourceVisionService
from .task_settings import AdmissionSettings
from .telemetry import EventProperties, TelemetryService
from .transformation_routes import router as transformation_router
from .transformations import TransformationService


def create_app(settings: Settings | None = None, transport=None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        with instance_lock(settings.data_dir):
            configure_logging()
            settings.prepare()
            db = Database(settings.data_dir / "app.db")
            db.migrate()
            app.state.files = FileMaintenance(db, settings)
            app.state.files.recover()
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(
                    settings.provider_timeout, connect=min(15, settings.provider_timeout)
                ),
                follow_redirects=False,
                transport=transport,
            ) as client:
                app.state.db = db
                app.state.task_settings = AdmissionSettings(db, settings)
                app.state.request_settings = AdmissionSettings(db, settings, requests=True)
                app.state.models = ModelService(
                    db,
                    SecretStore(settings.data_dir / "secrets"),
                    ModelGateway(client, lambda: app.state.request_settings.get()["concurrency"]),
                )
                app.state.notebooks = NotebookService(db)
                app.state.telemetry = TelemetryService(db, settings)
                app.state.jobs = JobService(
                    db,
                    app.state.telemetry,
                    concurrency=lambda: app.state.task_settings.get()["concurrency"],
                )
                app.state.sources = SourceService(db, settings, app.state.jobs)
                app.state.sources.vision = SourceVisionService(app.state.models, settings)
                app.state.retrieval = RetrievalService(db, app.state.models, app.state.sources)
                app.state.sources.indexer = app.state.retrieval
                app.state.indexes = IndexRebuildService(db, app.state.jobs, app.state.retrieval)
                app.state.models.indexes = app.state.indexes
                app.state.citations = CitationService(db, app.state.models, app.state.sources)
                app.state.chat = ChatService(
                    db, app.state.jobs, app.state.models, app.state.retrieval, app.state.citations
                )
                app.state.knowledge = KnowledgeService(
                    db, app.state.jobs, app.state.models, app.state.retrieval, app.state.citations
                )
                app.state.transformations = TransformationService(
                    db, app.state.jobs, app.state.knowledge
                )
                app.state.decks = DeckService(
                    db,
                    app.state.jobs,
                    app.state.models,
                    app.state.knowledge,
                    app.state.citations,
                    settings,
                )
                app.state.podcasts = PodcastService(
                    db,
                    app.state.jobs,
                    app.state.models,
                    app.state.knowledge,
                    app.state.citations,
                    settings,
                    app.state.decks.work_context,
                )
                app.state.mindmaps = MindMapService(
                    db,
                    app.state.jobs,
                    app.state.models,
                    app.state.knowledge,
                    app.state.citations,
                    settings,
                    app.state.decks.work_context,
                )
                app.state.composition = CompositionService(db, app.state.models, settings)
                app.state.assets = AssetService(
                    db, app.state.models, settings, app.state.composition.designs
                )
                app.state.decks.composition = app.state.composition
                app.state.decks.assets = app.state.assets
                app.state.pdf_exports = PDFExportService(db, app.state.jobs, settings)
                app.state.decks.exports = app.state.pdf_exports
                app.state.artifact_downloads = ArtifactDownloadService(
                    app.state.notebooks,
                    app.state.jobs,
                    {
                        "deck": DeckDownloadAdapter(db, app.state.pdf_exports, settings),
                        "podcast": PodcastDownloadAdapter(app.state.podcasts),
                        "mindmap": MindMapDownloadAdapter(app.state.mindmaps),
                    },
                )
                app.state.revisions = RevisionService(db, app.state.jobs, app.state.decks)
                app.state.decks.revisions = app.state.revisions
                app.state.pdf_exports.telemetry = app.state.telemetry
                app.state.telemetry.start()
                app.state.jobs.start()
                try:
                    yield
                finally:
                    try:
                        await app.state.jobs.stop()
                    finally:
                        app.state.artifact_downloads.close()
                        await app.state.telemetry.stop()

    app = FastAPI(
        title="OpenNoteLM",
        version=__version__,
        lifespan=lifespan,
        telemetry={
            "auto_configure": False,
            "tracing": False,
            "metrics": False,
            "logs": False,
            "operation_spans": False,
        },
    )
    app.include_router(source_router)
    app.include_router(chat_router)
    app.include_router(knowledge_router)
    app.include_router(transformation_router)
    app.include_router(deck_router)
    app.include_router(podcast_router)
    app.include_router(mindmap_router)
    app.include_router(artifact_download_router)
    app.include_router(artifact_instruction_router)
    app.include_router(render_router)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(settings.allowed_hosts))

    @app.middleware("http")
    async def same_origin(request: Request, call_next):
        origin = request.headers.get("origin")
        if origin and request.method not in ("GET", "HEAD", "OPTIONS"):
            parsed = urlsplit(origin)
            if parsed.netloc != request.headers.get("host") or parsed.scheme != request.url.scheme:
                return JSONResponse(
                    status_code=403,
                    content={
                        "error": {
                            "code": "ORIGIN_REJECTED",
                            "message": "Use this app's own browser page.",
                        }
                    },
                )
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: blob:; connect-src 'self'; font-src 'self'; "
            "object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
        )
        if request.url.path.startswith("/api/settings"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(AppError)
    async def app_error(request: Request, error: AppError):
        return JSONResponse(
            status_code=error.status,
            content={"error": {"code": error.code, "message": error.message}},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, error: RequestValidationError):
        # Pydantic's input fields can contain secrets. Return locations, never input values.
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Check the entered values.",
                    "fields": [".".join(str(part) for part in e["loc"]) for e in error.errors()],
                }
            },
        )

    @app.get("/api/health")
    def health():
        return {"status": "ok", "version": __version__}

    @app.get("/api/notebooks")
    def list_notebooks(request: Request):
        return request.app.state.notebooks.list()

    @app.post("/api/notebooks", status_code=201)
    def create_notebook(data: NotebookInput, request: Request):
        return request.app.state.notebooks.create(data)

    @app.get("/api/notebooks/{notebook_id}")
    def get_notebook(notebook_id: str, request: Request):
        return request.app.state.notebooks.get(notebook_id)

    @app.patch("/api/notebooks/{notebook_id}")
    def update_notebook(notebook_id: str, data: NotebookInput, request: Request):
        return request.app.state.notebooks.update(notebook_id, data)

    @app.delete("/api/notebooks/{notebook_id}", status_code=204)
    async def delete_notebook(notebook_id: str, request: Request):
        async with request.app.state.jobs.entity_lock("notebook:" + notebook_id):
            request.app.state.notebooks.delete(notebook_id)
            request.app.state.artifact_downloads.invalidate(notebook_id=notebook_id)
            request.app.state.files.drain()
        return Response(status_code=204)

    @app.get("/api/settings/models")
    def get_models(request: Request):
        return request.app.state.models.public_configs()

    @app.post("/api/settings/models/test")
    async def test_models(data: ModelTestInput, request: Request):
        try:
            result = await request.app.state.models.test_and_save(data.role, data)
        except AppError as error:
            request.app.state.telemetry.capture(
                "model_connection_tested", EventProperties(error_code=error.code)
            )
            raise
        request.app.state.telemetry.capture("model_connection_tested")
        return result

    @app.post("/api/settings/models/discover")
    async def discover_models(data: ModelTestInput, request: Request):
        return await request.app.state.models.discover(data.role, data)

    @app.get("/api/settings/models/embedding/indexes")
    def embedding_indexes(request: Request):
        return request.app.state.indexes.status()

    @app.post("/api/settings/models/embedding/indexes/rebuild", status_code=202)
    def rebuild_embedding_indexes(data: IndexRebuildInput, request: Request):
        return request.app.state.indexes.rebuild(data.mode)

    @app.post("/api/settings/models/vision-test")
    async def test_vision(request: Request):
        return await request.app.state.models.test_vision()

    @app.get("/api/settings/models/image-generation")
    def image_generation_settings(request: Request):
        return request.app.state.decks.image_generation_settings.get()

    @app.get("/api/settings/models/task-concurrency")
    def task_settings(request: Request):
        return request.app.state.task_settings.get()

    @app.put("/api/settings/models/task-concurrency")
    def save_task_settings(data: TaskConcurrencyInput, request: Request):
        return request.app.state.task_settings.save(data)

    @app.get("/api/settings/models/request-concurrency")
    def request_settings(request: Request):
        return request.app.state.request_settings.get()

    @app.put("/api/settings/models/request-concurrency")
    def save_request_settings(data: ModelRequestConcurrencyInput, request: Request):
        return request.app.state.request_settings.save(data)

    @app.put("/api/settings/models/image-generation")
    def save_image_generation_settings(data: ImageGenerationSettingsInput, request: Request):
        return request.app.state.decks.image_generation_settings.save(data)

    @app.get("/api/settings/models/speech-generation")
    def speech_settings(request: Request):
        return request.app.state.podcasts.speech_settings.get()

    @app.put("/api/settings/models/speech-generation")
    def save_speech_settings(data: SpeechGenerationSettingsInput, request: Request):
        return request.app.state.podcasts.speech_settings.save(data)

    @app.get("/api/settings/models/content-generation")
    def content_generation_settings(request: Request):
        return request.app.state.decks.content_generation_settings.get()

    @app.put("/api/settings/models/content-generation")
    def save_content_generation_settings(data: ContentGenerationSettingsInput, request: Request):
        return request.app.state.decks.content_generation_settings.save(data)

    @app.get("/api/settings/models/image-recognition")
    def image_recognition_settings(request: Request):
        return request.app.state.sources.vision.recognition_settings.get()

    @app.put("/api/settings/models/image-recognition")
    def save_image_recognition_settings(data: ImageRecognitionSettingsInput, request: Request):
        return request.app.state.sources.vision.recognition_settings.save(data)

    @app.get("/api/settings/preferences")
    def preferences(request: Request):
        with request.app.state.db.connect() as conn:
            row = conn.execute(
                "SELECT value_json FROM app_settings WHERE key='preferences'"
            ).fetchone()
        defaults = {"telemetry_enabled": False, "ui_language": None}
        return defaults | json.loads(row[0]) if row else defaults

    @app.put("/api/settings/preferences")
    async def set_preferences(data: PreferencesInput, request: Request):
        return await request.app.state.telemetry.set_preferences(
            data.model_dump(exclude_unset=True)
        )

    @app.get("/api/settings/telemetry")
    def telemetry_status(request: Request):
        return request.app.state.telemetry.status()

    @app.get("/api/diagnostics")
    def diagnostics(request: Request):
        return JSONResponse(
            diagnostic_report(request.app),
            headers={
                "Content-Disposition": 'attachment; filename="opennotelm-diagnostics.json"',
                "Cache-Control": "no-store",
            },
        )

    if (settings.frontend_dir / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=settings.frontend_dir / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def frontend(path: str):
        if path.startswith("api/"):
            raise AppError("NOT_FOUND", "API route not found.", 404)
        index: Path = settings.frontend_dir / "index.html"
        if not index.is_file():
            raise AppError(
                "FRONTEND_NOT_BUILT", "Build the frontend or use the development server.", 503
            )
        return FileResponse(index)

    return app


app = create_app()
