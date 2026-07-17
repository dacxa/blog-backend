from logging.config import fileConfig
import os

from alembic import context
from sqlalchemy import engine_from_config, pool

config = context.config
PLACEHOLDER_DATABASE_URL = "driver://user:pass@localhost/dbname"

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = None


def database_url() -> str:
    """Get an explicitly supplied migration URL without loading app settings."""
    url = os.environ.get("ALEMBIC_DATABASE_URL") or config.get_main_option("sqlalchemy.url")
    if not url or url == PLACEHOLDER_DATABASE_URL:
        raise RuntimeError(
            "A database URL is required for Alembic. Set ALEMBIC_DATABASE_URL "
            "or explicitly configure sqlalchemy.url."
        )
    return url


def run_migrations_offline() -> None:
    """Run migrations without creating an Engine."""
    url = database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        output_buffer=config.output_buffer,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations with the URL provided by Alembic configuration."""
    configuration = config.get_section(config.config_ini_section, {}).copy()
    configuration["sqlalchemy.url"] = database_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
