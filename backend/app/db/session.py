"""One SQLAlchemy session per database-backed API request."""

from collections.abc import Iterator

from fastapi import HTTPException, Request, status
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker


def create_session_factory(engine: Engine | None) -> sessionmaker[Session] | None:
    """Bind a session factory to the configured database engine."""

    if engine is None:
        return None

    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db(request: Request) -> Iterator[Session]:
    """Provide a session to a route and close it after the request."""

    session_factory: sessionmaker[Session] | None = request.app.state.session_factory
    if session_factory is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable",
        )

    db = session_factory()
    try:
        yield db
    finally:
        db.close()
