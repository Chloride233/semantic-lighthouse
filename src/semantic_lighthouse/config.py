from functools import lru_cache
import os

from pydantic import BaseModel


class Settings(BaseModel):
    database_url: str = "postgresql+psycopg://semantic_lighthouse:semantic_lighthouse@localhost:5432/semantic_lighthouse"
    jwt_secret_key: str = "change-me-in-dev-at-least-32-bytes"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30
    refresh_cookie_name: str = "semantic_lighthouse_refresh"
    cookie_secure: bool = False
    cookie_samesite: str = "lax"
    knowledge_base_path: str = r"F:\ontology-kb\knowledge-graph"
    max_markdown_upload_bytes: int = 1024 * 1024
    document_storage_path: str = "./document-storage"
    upload_tmp_path: str = "./upload-tmp"
    max_document_upload_bytes: int = 50 * 1024 * 1024
    upload_session_expire_hours: int = 24
    upload_chunk_bytes: int = 2 * 1024 * 1024
    embedding_provider: str = "aliyun"
    dashscope_api_key: str | None = None
    embedding_model: str = "text-embedding-v4"
    embedding_dimension: int = 1024
    embedding_batch_size: int = 16
    embedding_timeout_seconds: int = 30
    chat_provider: str = "deepseek"
    deepseek_api_key: str | None = None
    chat_base_url: str = "https://api.deepseek.com"
    chat_model: str = "deepseek-v4-flash"
    chat_timeout_seconds: int = 60
    rag_top_k: int = 5
    rag_max_context_chars: int = 6000
    chunk_target_chars: int = 800
    chunk_max_chars: int = 1200
    chunk_min_chars: int = 200
    chunk_overlap_chars: int = 0
    ingestion_max_attempts: int = 3
    agent_max_steps: int = 5
    app_env: str = "development"

    def validate_runtime_safety(self) -> None:
        """Raise ValueError if production settings are unsafe."""
        if self.app_env != "production":
            return
        errors: list[str] = []
        default_jwt = Settings.model_fields["jwt_secret_key"].default
        if self.jwt_secret_key == default_jwt:
            errors.append("JWT_SECRET_KEY must not use the default placeholder in production")
        if len(self.jwt_secret_key) < 32:
            errors.append("JWT_SECRET_KEY must be at least 32 characters in production")
        if not self.cookie_secure:
            errors.append("COOKIE_SECURE must be true in production")
        default_db = Settings.model_fields["database_url"].default
        if self.database_url == default_db:
            errors.append("DATABASE_URL must not use the default local development connection string in production")
        if errors:
            raise ValueError("Production safety checks failed: " + "; ".join(errors))


def _bool_from_env(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def _str_from_env(name: str, default: str) -> str:
    return os.getenv(name, default).strip()


@lru_cache
def get_settings() -> Settings:
    return Settings(
        database_url=_str_from_env("DATABASE_URL", Settings.model_fields["database_url"].default),
        jwt_secret_key=_str_from_env("JWT_SECRET_KEY", Settings.model_fields["jwt_secret_key"].default),
        jwt_algorithm=_str_from_env("JWT_ALGORITHM", Settings.model_fields["jwt_algorithm"].default),
        access_token_expire_minutes=int(
            os.getenv(
                "ACCESS_TOKEN_EXPIRE_MINUTES",
                str(Settings.model_fields["access_token_expire_minutes"].default),
            )
        ),
        refresh_token_expire_days=int(
            os.getenv(
                "REFRESH_TOKEN_EXPIRE_DAYS",
                str(Settings.model_fields["refresh_token_expire_days"].default),
            )
        ),
        refresh_cookie_name=_str_from_env(
            "REFRESH_COOKIE_NAME",
            Settings.model_fields["refresh_cookie_name"].default,
        ),
        cookie_secure=_bool_from_env(
            os.getenv("COOKIE_SECURE"),
            Settings.model_fields["cookie_secure"].default,
        ),
        cookie_samesite=_str_from_env("COOKIE_SAMESITE", Settings.model_fields["cookie_samesite"].default),
        knowledge_base_path=_str_from_env(
            "KNOWLEDGE_BASE_PATH",
            Settings.model_fields["knowledge_base_path"].default,
        ),
        max_markdown_upload_bytes=int(
            os.getenv(
                "MAX_MARKDOWN_UPLOAD_BYTES",
                str(Settings.model_fields["max_markdown_upload_bytes"].default),
            )
        ),
        document_storage_path=_str_from_env(
            "DOCUMENT_STORAGE_PATH",
            Settings.model_fields["document_storage_path"].default,
        ),
        upload_tmp_path=_str_from_env("UPLOAD_TMP_PATH", Settings.model_fields["upload_tmp_path"].default),
        max_document_upload_bytes=int(
            os.getenv(
                "MAX_DOCUMENT_UPLOAD_BYTES",
                str(Settings.model_fields["max_document_upload_bytes"].default),
            )
        ),
        upload_session_expire_hours=int(
            os.getenv(
                "UPLOAD_SESSION_EXPIRE_HOURS",
                str(Settings.model_fields["upload_session_expire_hours"].default),
            )
        ),
        upload_chunk_bytes=int(os.getenv("UPLOAD_CHUNK_BYTES", str(Settings.model_fields["upload_chunk_bytes"].default))),
        embedding_provider=_str_from_env("EMBEDDING_PROVIDER", Settings.model_fields["embedding_provider"].default),
        dashscope_api_key=(os.getenv("DASHSCOPE_API_KEY") or "").strip() or None,
        embedding_model=_str_from_env("EMBEDDING_MODEL", Settings.model_fields["embedding_model"].default),
        embedding_dimension=int(
            os.getenv("EMBEDDING_DIMENSION", str(Settings.model_fields["embedding_dimension"].default))
        ),
        embedding_batch_size=int(
            os.getenv("EMBEDDING_BATCH_SIZE", str(Settings.model_fields["embedding_batch_size"].default))
        ),
        embedding_timeout_seconds=int(
            os.getenv(
                "EMBEDDING_TIMEOUT_SECONDS",
                str(Settings.model_fields["embedding_timeout_seconds"].default),
            )
        ),
        chat_provider=_str_from_env("CHAT_PROVIDER", Settings.model_fields["chat_provider"].default),
        deepseek_api_key=(os.getenv("DEEPSEEK_API_KEY") or "").strip() or None,
        chat_base_url=_str_from_env("CHAT_BASE_URL", Settings.model_fields["chat_base_url"].default),
        chat_model=_str_from_env("CHAT_MODEL", Settings.model_fields["chat_model"].default),
        chat_timeout_seconds=int(
            os.getenv("CHAT_TIMEOUT_SECONDS", str(Settings.model_fields["chat_timeout_seconds"].default))
        ),
        rag_top_k=int(os.getenv("RAG_TOP_K", str(Settings.model_fields["rag_top_k"].default))),
        rag_max_context_chars=int(
            os.getenv("RAG_MAX_CONTEXT_CHARS", str(Settings.model_fields["rag_max_context_chars"].default))
        ),
        chunk_target_chars=int(
            os.getenv("CHUNK_TARGET_CHARS", str(Settings.model_fields["chunk_target_chars"].default))
        ),
        chunk_max_chars=int(os.getenv("CHUNK_MAX_CHARS", str(Settings.model_fields["chunk_max_chars"].default))),
        chunk_min_chars=int(os.getenv("CHUNK_MIN_CHARS", str(Settings.model_fields["chunk_min_chars"].default))),
        chunk_overlap_chars=int(
            os.getenv("CHUNK_OVERLAP_CHARS", str(Settings.model_fields["chunk_overlap_chars"].default))
        ),
        ingestion_max_attempts=int(
            os.getenv("INGESTION_MAX_ATTEMPTS", str(Settings.model_fields["ingestion_max_attempts"].default))
        ),
        agent_max_steps=int(os.getenv("AGENT_MAX_STEPS", str(Settings.model_fields["agent_max_steps"].default))),
        app_env=_str_from_env("APP_ENV", Settings.model_fields["app_env"].default),
    )
