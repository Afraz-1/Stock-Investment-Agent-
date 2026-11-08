"""Run schema migrations using EquityIQ's configured PostgreSQL database."""

from alembic import context

from app.core.config import Settings
from app.db.connection import create_database_engine
from app.models import Base


settings = Settings()
if settings.database_url is None:
    raise RuntimeError("EQUITYIQ_DATABASE_URL is required for migrations")

engine = create_database_engine(settings.database_url.get_secret_value())
if engine is None:
    raise RuntimeError("A PostgreSQL database URL is required for migrations")

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Generate SQL without connecting to the database."""

    context.configure(
        url=engine.url.render_as_string(hide_password=False),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Apply migrations to the configured database."""

    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


try:
    if context.is_offline_mode():
        run_migrations_offline()
    else:
        run_migrations_online()
finally:
    engine.dispose()
