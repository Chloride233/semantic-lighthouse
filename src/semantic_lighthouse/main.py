from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select, text

from semantic_lighthouse.config import get_settings
from semantic_lighthouse.database import SessionLocal
from semantic_lighthouse.models import Document, IngestionJob, utc_now
from semantic_lighthouse.routers import agent, auth, conversations, datasets, documents, groups, ontology, projects, rag, tasks


class NoCacheStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope: dict) -> Response:
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-store"
        return response


def _recover_orphaned_jobs() -> None:
    """Mark orphaned ingestion jobs and documents after a crash.

    - ``running`` jobs → ``failed`` (the process died mid-ETL).
    - ``processing`` documents with no ``running`` job → ``uploaded``.

    Failures are swallowed so that a missing database or table
    (e.g. in test environments before migrations) does not prevent
    the API from starting.
    """
    try:
        db = SessionLocal()
        try:
            orphaned_jobs = db.scalars(
                select(IngestionJob).where(IngestionJob.status == "running")
            ).all()
            for job in orphaned_jobs:
                job.status = "failed"
                job.error_message = "Server restarted during ingestion"
                job.finished_at = utc_now()

            orphaned_docs = db.scalars(
                select(Document).where(Document.status == "processing")
            ).all()
            for doc in orphaned_docs:
                running_job = db.scalar(
                    select(IngestionJob).where(
                        IngestionJob.document_id == doc.id,
                        IngestionJob.status == "running",
                    )
                )
                if running_job is None:
                    doc.status = "uploaded"

            db.commit()
        finally:
            db.close()
    except Exception:
        pass  # DB or table not ready yet — harmless at startup


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
    _recover_orphaned_jobs()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Semantic Lighthouse API",
        description="Enterprise authentication, group permissions, and permission-aware document retrieval.",
        version="0.1.0",
        lifespan=lifespan,
    )

    @app.middleware("http")
    async def _request_id_middleware(request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid4()))
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    @app.get("/health")
    def health() -> dict:
        result: dict = {"status": "ok", "database": "unknown", "chat_provider": "unknown", "embedding_provider": "unknown"}
        try:
            db = SessionLocal()
            try:
                db.execute(text("SELECT 1"))
                result["database"] = "connected"
            finally:
                db.close()
        except Exception:
            result["database"] = "unavailable"
        try:
            settings = get_settings()
            result["chat_provider"] = settings.chat_provider
            result["embedding_provider"] = settings.embedding_provider
        except Exception:
            pass
        return result

    app.include_router(auth.router)
    app.include_router(groups.router)
    app.include_router(documents.router)
    app.include_router(rag.router)
    app.include_router(conversations.router)
    app.include_router(agent.router)
    app.include_router(tasks.router)
    app.include_router(projects.router)
    app.include_router(datasets.router)
    app.include_router(ontology.router)
    app.include_router(ontology.project_model_router)


    static_dir = Path(__file__).resolve().parents[2] / "static"
    app.mount("/static", NoCacheStaticFiles(directory=static_dir), name="static")

    @app.get("/console", include_in_schema=False)
    def console() -> FileResponse:
        response = FileResponse(static_dir / "console.html")
        response.headers["Cache-Control"] = "no-store"
        return response

    return app


app = create_app()
