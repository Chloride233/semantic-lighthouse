"""Production safety configuration tests."""
import pytest
from semantic_lighthouse.config import Settings


class TestProductionSafety:
    def test_development_default_no_error(self):
        """Default settings (development) pass validation without error."""
        s = Settings(
            database_url="sqlite+pysqlite:///:memory:",
            jwt_secret_key="test-secret-key-at-least-32-bytes",
        )
        s.validate_runtime_safety()  # should not raise

    def test_production_default_jwt_fails(self):
        """Production + default JWT_SECRET_KEY must raise."""
        s = Settings(
            app_env="production",
            database_url="sqlite+pysqlite:///:memory:",
            jwt_secret_key="change-me-in-dev-at-least-32-bytes",
        )
        with pytest.raises(ValueError, match="JWT_SECRET_KEY"):
            s.validate_runtime_safety()

    def test_production_short_jwt_fails(self):
        """Production + JWT_SECRET_KEY < 32 chars must raise."""
        s = Settings(
            app_env="production",
            database_url="postgresql+psycopg://user:pass@host:5432/db",
            jwt_secret_key="too-short",
        )
        with pytest.raises(ValueError, match="JWT_SECRET_KEY"):
            s.validate_runtime_safety()

    def test_production_cookie_secure_false_fails(self):
        """Production + COOKIE_SECURE=false must raise."""
        s = Settings(
            app_env="production",
            database_url="postgresql+psycopg://user:pass@host:5432/db",
            jwt_secret_key="this-is-at-least-32-chars-long-key!!",
            cookie_secure=False,
        )
        with pytest.raises(ValueError, match="COOKIE_SECURE"):
            s.validate_runtime_safety()

    def test_production_default_database_url_fails(self):
        """Production + default DATABASE_URL must raise."""
        default_db = Settings.model_fields["database_url"].default
        s = Settings(
            app_env="production",
            database_url=default_db,
            jwt_secret_key="this-is-at-least-32-chars-long-key!!",
            cookie_secure=True,
        )
        with pytest.raises(ValueError, match="DATABASE_URL"):
            s.validate_runtime_safety()

    def test_production_valid_config_passes(self):
        """Production + valid config passes validation."""
        s = Settings(
            app_env="production",
            database_url="postgresql+psycopg://real:pass@host:5432/real",
            jwt_secret_key="this-is-at-least-32-chars-long-key!!",
            cookie_secure=True,
        )
        s.validate_runtime_safety()  # should not raise
