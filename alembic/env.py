import os
from logging.config import fileConfig
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool

from alembic import context
from src.database.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

db_url = os.environ.get("DATABASE_URL", config.get_main_option("sqlalchemy.url"))
if db_url and db_url.startswith("postgresql+asyncpg://"):
    db_url = db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
elif db_url and "+aiosqlite" in db_url:
    db_url = db_url.replace("+aiosqlite", "", 1)
config.set_main_option("sqlalchemy.url", db_url or "")

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
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
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
