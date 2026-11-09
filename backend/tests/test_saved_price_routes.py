"""Read saved prices through the HTTP API without contacting Yahoo."""

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.main import app
from app.models import Base, DailyPrice
from app.services.market_data.registration import register_listing


@pytest.fixture
def saved_prices(tmp_path):
    engine = create_engine(f"sqlite+pysqlite:///{(tmp_path / 'saved.db').as_posix()}")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        listing = register_listing(
            db, exchange_code="NSE", symbol="TCS",
            legal_name="Tata Consultancy Services Limited",
        )
        db.add(
            DailyPrice(
                security_id=listing.id,
                trading_day=date(2026, 11, 6),
                provider="yahoo_finance",
                adjustment="dividend_adjusted",
                currency_code="INR",
                open=Decimal("100"), high=Decimal("105"),
                low=Decimal("99"), close=Decimal("103"), volume=1000,
                source_retrieved_at=datetime(2026, 11, 9, tzinfo=timezone.utc),
            )
        )
        db.commit()

    def test_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = test_db
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_saved_prices_returns_bars_and_freshness(saved_prices) -> None:
    response = TestClient(app).get(
        "/api/v1/stocks/NSE/TCS/saved-prices",
        params={"start": "2026-11-02", "end": "2026-11-06"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["security"] == {"exchange_code": "NSE", "symbol": "TCS"}
    assert data["provider"] == "yahoo_finance"
    assert data["adjustment"] == "dividend_adjusted"
    assert data["bars"][0]["close"] == "103.00000000"
    assert data["newest_retrieved_at"].startswith("2026-11-09")
    assert data["unavailable_reason"] is None


def test_saved_prices_distinguishes_no_data_from_unknown_listing(saved_prices) -> None:
    client = TestClient(app)
    empty = client.get(
        "/api/v1/stocks/NSE/TCS/saved-prices",
        params={"start": "2026-10-01", "end": "2026-10-02"},
    )
    assert empty.status_code == 200
    assert empty.json()["bars"] == []
    assert empty.json()["unavailable_reason"] == "no_data"

    missing = client.get(
        "/api/v1/stocks/BSE/TCS/saved-prices",
        params={"start": "2026-11-02", "end": "2026-11-06"},
    )
    assert missing.status_code == 404


def test_saved_prices_rejects_reversed_dates(saved_prices) -> None:
    response = TestClient(app).get(
        "/api/v1/stocks/NSE/TCS/saved-prices",
        params={"start": "2026-11-06", "end": "2026-11-02"},
    )
    assert response.status_code == 422
