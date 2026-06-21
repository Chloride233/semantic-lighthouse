from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool, text

from semantic_lighthouse.config import get_settings
from semantic_lighthouse.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_num_length=64,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        # Ensure alembic_version.version_num supports this project's
        # revision IDs (up to 39 chars). The Alembic default is
        # VARCHAR(32), which is too short for PostgreSQL.
        # SQLite ignores VARCHAR width, so this is PG-only.
        if connection.dialect.name == "postgresql":
            connection.execute(
                text("ROLLBACK")
            )  # ensure clean state
            # Create or widen the table outside Alembic's transaction
            connection.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS alembic_version "
                    "(version_num VARCHAR(64) NOT NULL PRIMARY KEY)"
                )
            )
            connection.execute(
                text(
                    "ALTER TABLE alembic_version ALTER COLUMN version_num "
                    "TYPE VARCHAR(64)"
                )
            )
            connection.commit()

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            version_num_length=64,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

