"""PostgreSQL engine creation and connection checks."""

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.exc import SQLAlchemyError


def create_database_engine(database_url: str | None) -> Engine | None:
    """Build a lazy PostgreSQL engine, or return None if unconfigured."""

    if database_url is None:
        return None

    url = make_url(database_url)
    if url.drivername != "postgresql+psycopg":
        raise ValueError("Database URL must use the postgresql+psycopg driver")

    return create_engine(
        url,
        pool_pre_ping=True,
        connect_args={"connect_timeout": 3},
    )


def database_is_ready(engine: Engine | None) -> bool:
    """Return whether the database answers a simple SQL query."""

    if engine is None:
        return False

    try:
        with engine.connect() as connection:
            return connection.execute(text("SELECT 1")).scalar_one() == 1
    except SQLAlchemyError:
        return False
