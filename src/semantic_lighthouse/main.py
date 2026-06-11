from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from semantic_lighthouse.database import SessionLocal
from semantic_lighthouse.models import Document, IngestionJob, utc_now
from semantic_lighthouse.routers import auth, documents, groups, rag


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

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(auth.router)
    app.include_router(groups.router)
    app.include_router(documents.router)
    app.include_router(rag.router)

    static_dir = Path(__file__).resolve().parents[2] / "static"
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/console", include_in_schema=False)
    def console() -> FileResponse:
        return FileResponse(static_dir / "console.html")

    return app


app = create_app()
