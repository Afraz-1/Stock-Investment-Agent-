"""Offline tests for the per-request database session dependency."""

from typing import Annotated
from unittest.mock import Mock

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.db.session import create_session_factory, get_db


def test_database_session_can_run_query() -> None:
    test_engine = create_engine("sqlite+pysqlite:///:memory:")
    test_app = FastAPI()
    test_app.state.session_factory = create_session_factory(test_engine)

    @test_app.get("/probe")
    def probe(db: Annotated[Session, Depends(get_db)]) -> dict[str, int]:
        return {"value": db.execute(text("SELECT 1")).scalar_one()}

    try:
        response = TestClient(test_app).get("/probe")
    finally:
        test_engine.dispose()

    assert response.status_code == 200
    assert response.json() == {"value": 1}


def test_database_session_is_unavailable_without_engine() -> None:
    test_app = FastAPI()
    test_app.state.session_factory = create_session_factory(None)

    @test_app.get("/probe")
    def probe(db: Annotated[Session, Depends(get_db)]) -> dict[str, str]:
        return {"status": "connected"}

    response = TestClient(test_app).get("/probe")

    assert response.status_code == 503
    assert response.json() == {"detail": "Database unavailable"}


def test_database_session_is_closed_after_request() -> None:
    test_app = FastAPI()
    fake_session = Mock(spec=Session)
    test_app.state.session_factory = Mock(return_value=fake_session)

    @test_app.get("/probe")
    def probe(db: Annotated[Session, Depends(get_db)]) -> dict[str, str]:
        return {"status": "ok"}

    response = TestClient(test_app).get("/probe")

    assert response.status_code == 200
    fake_session.close.assert_called_once_with()
