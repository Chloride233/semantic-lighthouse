import os
import tempfile
from collections.abc import Generator
from unittest import mock

os.environ["JWT_SECRET_KEY"] = "test-secret-key-at-least-32-bytes"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from semantic_lighthouse.config import Settings, get_settings
from semantic_lighthouse.database import get_db
from semantic_lighthouse.main import create_app
from semantic_lighthouse.models import Base
import semantic_lighthouse.routers.documents as documents_router


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
    app = create_app()

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

    # Patch SessionLocal so that BackgroundTasks use the same file-backed DB.
    test_sessionmaker = sessionmaker(bind=db_session.get_bind(), autoflush=False, autocommit=False)
    with mock.patch.object(documents_router, "SessionLocal", test_sessionmaker):
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
