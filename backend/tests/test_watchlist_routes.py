"""Exercise watchlist writes and price refresh without live Yahoo requests."""

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.api.v1.stocks import get_market_data_provider
from app.db.session import get_db
from app.main import app
from app.models import Base, Company, DailyPrice, Security, WatchlistItem
from app.services.market_data.provider import MarketDataError, MarketDataProvider
from app.services.market_data.schemas import CompanyProfile, MarketDataSource, PriceBar, PriceHistory, SecurityKey, SecuritySearchResult


class FakeProvider(MarketDataProvider):
    available = True
    fail_prices = False

    def search(self, query: str, limit: int) -> list[SecuritySearchResult]:
        return []

    def get_profile(self, security: SecurityKey) -> CompanyProfile | None:
        if not self.available:
            return None
        return CompanyProfile(
            security=security,
            company_name="Example Limited",
            isin="INE000A01000",
            currency_code="INR",
            source=MarketDataSource(provider="yahoo_finance", retrieved_at=datetime(2026, 11, 9, tzinfo=timezone.utc)),
        )

    def get_prices(self, security: SecurityKey, start_date: date, end_date: date) -> PriceHistory:
        if self.fail_prices:
            raise MarketDataError("private upstream error")
        return PriceHistory(
            security=security,
            currency_code="INR",
            adjustment="dividend_adjusted",
            bars=[PriceBar(trading_day=start_date, open=Decimal("100"), high=Decimal("105"), low=Decimal("99"), close=Decimal("103"), volume=1000)],
            source=MarketDataSource(provider="yahoo_finance", retrieved_at=datetime(2026, 11, 9, tzinfo=timezone.utc)),
        )


@pytest.fixture
def local_app(tmp_path):
    engine = create_engine(f"sqlite+pysqlite:///{(tmp_path / 'watchlist.db').as_posix()}")
    Base.metadata.create_all(engine)
    provider = FakeProvider()

    def test_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = test_db
    app.dependency_overrides[get_market_data_provider] = lambda: provider
    try:
        yield TestClient(app), engine, provider
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_market_data_provider, None)
        engine.dispose()


def _body(exchange: str = "NSE") -> dict:
    return {
        "exchange_code": exchange,
        "symbol": "EXAMPLE",
        "legal_name": "Example Limited",
        "isin": "INE000A01000",
    }


def test_add_list_repeat_and_reuse_company_across_exchanges(local_app) -> None:
    client, engine, _ = local_app
    assert client.get("/api/v1/watchlist").json() == []

    added = client.post("/api/v1/watchlist", json=_body())
    assert added.status_code == 201
    assert added.json()["saved_price_count"] == 0
    assert added.json()["security"] == {"exchange_code": "NSE", "symbol": "EXAMPLE"}
    assert client.post("/api/v1/watchlist", json=_body()).status_code == 200
    assert client.post("/api/v1/watchlist", json=_body("BSE")).status_code == 201
    assert len(client.get("/api/v1/watchlist").json()) == 2

    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(Company)) == 1
        assert db.scalar(select(func.count()).select_from(Security)) == 2
        assert db.scalar(select(func.count()).select_from(WatchlistItem)) == 2


def test_refresh_and_remove_preserve_saved_prices(local_app) -> None:
    client, engine, _ = local_app
    client.post("/api/v1/watchlist", json=_body())
    path = "/api/v1/watchlist/NSE/EXAMPLE/refresh-prices"
    params = {"start": "2026-11-06", "end": "2026-11-06"}
    assert client.post(path, params=params).json()["bars_received"] == 1
    assert client.post(path, params=params).json()["bars_received"] == 1
    tracked = client.get("/api/v1/watchlist").json()[0]
    assert tracked["saved_price_count"] == 1
    assert tracked["latest_saved_day"] == "2026-11-06"
    assert client.delete("/api/v1/watchlist/NSE/EXAMPLE").status_code == 204
    assert client.get("/api/v1/watchlist").json() == []
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(DailyPrice)) == 1
        assert db.scalar(select(func.count()).select_from(Security)) == 1
    assert client.post("/api/v1/watchlist", json=_body()).json()["saved_price_count"] == 1


def test_invalid_listing_range_and_provider_failure(local_app) -> None:
    client, engine, provider = local_app
    provider.available = False
    assert client.post("/api/v1/watchlist", json=_body()).status_code == 404
    provider.available = True
    assert client.post("/api/v1/watchlist", json={**_body(), "legal_name": ""}).status_code == 422
    assert client.post("/api/v1/watchlist", json=_body()).status_code == 201
    path = "/api/v1/watchlist/NSE/EXAMPLE/refresh-prices"
    assert client.post(path, params={"start": "2026-11-07", "end": "2026-11-06"}).status_code == 422
    assert client.post(path, params={"start": "2025-01-01", "end": "2026-11-06"}).status_code == 422
    assert client.post("/api/v1/watchlist/BSE/EXAMPLE/refresh-prices", params={"start": "2026-11-06", "end": "2026-11-06"}).status_code == 404
    provider.fail_prices = True
    assert client.post(path, params={"start": "2026-11-06", "end": "2026-11-06"}).status_code == 502
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(DailyPrice)) == 0
