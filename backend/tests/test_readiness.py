"""Offline tests for database readiness."""

from unittest.mock import Mock

from fastapi.testclient import TestClient
from pytest import MonkeyPatch, raises
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError

from app import main
from app.db.connection import create_database_engine


def test_readiness_is_unavailable_without_database(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(main, "engine", None)

    response = TestClient(main.app).get("/api/v1/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "not_ready", "database": "unavailable"}


def test_readiness_queries_database(monkeypatch: MonkeyPatch) -> None:
    # SQLite keeps this test offline; PostgreSQL is the configured production driver.
    test_engine = create_engine("sqlite+pysqlite:///:memory:")
    monkeypatch.setattr(main, "engine", test_engine)

    try:
        response = TestClient(main.app).get("/api/v1/ready")
    finally:
        test_engine.dispose()

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "database": "connected"}


def test_database_engine_rejects_wrong_driver() -> None:
    with raises(ValueError, match="postgresql\\+psycopg"):
        create_database_engine("sqlite+pysqlite:///:memory:")


def test_readiness_is_unavailable_when_connection_fails(monkeypatch: MonkeyPatch) -> None:
    failing_engine = Mock()
    failing_engine.connect.side_effect = OperationalError(
        "SELECT 1", {}, Exception("database unavailable")
    )
    monkeypatch.setattr(main, "engine", failing_engine)

    response = TestClient(main.app).get("/api/v1/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "not_ready", "database": "unavailable"}
