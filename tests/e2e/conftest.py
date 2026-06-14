import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
import uuid
from collections.abc import Generator
from pathlib import Path
from unittest import mock

os.environ["JWT_SECRET_KEY"] = "test-secret-key-at-least-32-bytes"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from semantic_lighthouse.config import Settings, get_settings
from semantic_lighthouse.database import get_db
from semantic_lighthouse.models import Base
import semantic_lighthouse.main as app_main
import semantic_lighthouse.routers.documents as documents_router


ROOT = Path(__file__).resolve().parents[2]
RUNTIME_DIR = ROOT / ".tmp" / "e2e-runtime"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _wait_for_health(base_url: str, proc: subprocess.Popen[bytes]) -> None:
    deadline = time.time() + 20
    last_error: Exception | None = None
    while time.time() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(f"E2E server exited early with code {proc.returncode}")
        try:
            with urllib.request.urlopen(f"{base_url}/health", timeout=1) as response:
                if response.status == 200:
                    return
        except Exception as exc:  # noqa: BLE001 - diagnostics are kept for timeout.
            last_error = exc
        time.sleep(0.25)
    raise RuntimeError(f"E2E server did not become healthy: {last_error}")


@pytest.fixture(scope="session")
def base_url() -> Generator[str]:
    """Start an isolated local API/UI server for browser tests."""
    external = os.environ.get("SEMANTIC_LIGHTHOUSE_E2E_BASE_URL")
    if external:
        yield external.rstrip("/")
        return

    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    db_path = RUNTIME_DIR / f"e2e-{uuid.uuid4().hex}.db"
    log_path = RUNTIME_DIR / "server.log"
    port = _free_port()
    base = f"http://127.0.0.1:{port}"

    env = os.environ.copy()
    env.update(
        DATABASE_URL=f"sqlite+pysqlite:///{db_path.as_posix()}",
        JWT_SECRET_KEY="e2e-secret-key-at-least-32-bytes",
        COOKIE_SECURE="false",
        CHAT_PROVIDER="fake",
        CHAT_MODEL="fake",
        EMBEDDING_PROVIDER="fake",
        EMBEDDING_MODEL="fake",
        EMBEDDING_DIMENSION="8",
    )

    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
    )

    with log_path.open("ab") as log_file:
        proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "semantic_lighthouse.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ],
            cwd=ROOT,
            env=env,
            stdout=log_file,
            stderr=subprocess.STDOUT,
        )

        try:
            _wait_for_health(base, proc)
            yield base
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=10)
            try:
                db_path.unlink()
            except OSError:
                pass


@pytest.fixture()
def db_session() -> Generator[Session]:
    """File-backed SQLite so BackgroundTasks threads can share the same DB."""
    fd, path = tempfile.mkstemp(suffix=".db", prefix="sl_test_")
    os.close(fd)
    engine = create_engine(f"sqlite+pysqlite:///{path}")
    testing_session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)
    session = testing_session_local()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
        try:
            os.unlink(path)
        except OSError:
            pass


@pytest.fixture()
def client(db_session: Session) -> Generator[TestClient]:
    app = app_main.create_app()

    def override_get_db() -> Generator[Session]:
        yield db_session

    def override_get_settings() -> Settings:
        return Settings(
            database_url="sqlite+pysqlite:///:memory:",
            jwt_secret_key="test-secret-key-at-least-32-bytes",
            cookie_secure=False,
            cookie_samesite="lax",
        )

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = override_get_settings

    # Patch SessionLocal so that lifespan recovery and BackgroundTasks use the same file-backed DB.
    test_sessionmaker = sessionmaker(bind=db_session.get_bind(), autoflush=False, autocommit=False)
    with (
        mock.patch.object(app_main, "SessionLocal", test_sessionmaker),
        mock.patch.object(documents_router, "SessionLocal", test_sessionmaker),
    ):
        with TestClient(app) as test_client:
            yield test_client


def register_and_login(client: TestClient, email: str, password: str = "Passw0rd!"):
    register_response = client.post(
        "/auth/register",
        json={"email": email, "password": password, "display_name": email.split("@")[0]},
    )
    assert register_response.status_code == 201
    login_response = client.post("/auth/login", json={"email": email, "password": password})
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    return register_response.json(), login_response, headers
