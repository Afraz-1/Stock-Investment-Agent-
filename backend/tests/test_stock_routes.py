"""Exercise the stock HTTP boundary without calling Yahoo Finance."""

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.api.v1.stocks import get_market_data_provider
from app.main import app
from app.services.market_data.provider import MarketDataError, MarketDataProvider
from app.services.market_data.schemas import (
    CompanyProfile,
    CompanyFacts,
    MarketDataSource,
    PriceBar,
    PriceHistory,
    SecurityKey,
    SecuritySearchResult,
)


class FakeProvider(MarketDataProvider):
    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self.profile_available = True
        self.fail = False

    def search(self, query: str, limit: int) -> list[SecuritySearchResult]:
        self.calls.append(("search", query, limit))
        if self.fail:
            raise MarketDataError("private provider detail")
        return [
            SecuritySearchResult(
                security=SecurityKey(exchange_code="NSE", symbol="TCS"),
                company_name="Tata Consultancy Services",
                currency_code="INR",
                source=self._source(),
            )
        ]

    def get_profile(self, security: SecurityKey) -> CompanyProfile | None:
        self.calls.append(("profile", security))
        if not self.profile_available:
            return None
        return CompanyProfile(
            security=security,
            company_name="Tata Consultancy Services",
            country_code="IN",
            facts=CompanyFacts(market_cap=Decimal("1000000000000"), trailing_pe=Decimal("20.5")),
            source=self._source(),
        )

    def get_prices(
        self, security: SecurityKey, start_date: date, end_date: date
    ) -> PriceHistory:
        self.calls.append(("prices", security, start_date, end_date))
        return PriceHistory(
            security=security,
            currency_code="INR",
            adjustment="dividend_adjusted",
            bars=[
                PriceBar(
                    trading_day=start_date,
                    open=Decimal("100"),
                    high=Decimal("105"),
                    low=Decimal("99"),
                    close=Decimal("103"),
                    volume=1000,
                )
            ],
            source=self._source(),
        )

    @staticmethod
    def _source() -> MarketDataSource:
        return MarketDataSource(
            provider="fake", retrieved_at=datetime(2026, 11, 8, tzinfo=timezone.utc)
        )


@pytest.fixture
def fake_provider():
    provider = FakeProvider()
    app.dependency_overrides[get_market_data_provider] = lambda: provider
    try:
        yield provider
    finally:
        app.dependency_overrides.pop(get_market_data_provider, None)


def test_search_route_validates_and_returns_listings(fake_provider: FakeProvider) -> None:
    client = TestClient(app)
    response = client.get("/api/v1/stocks/search", params={"q": " TCS ", "limit": 3})
    assert response.status_code == 200
    assert response.json()[0]["security"] == {"exchange_code": "NSE", "symbol": "TCS"}
    assert fake_provider.calls == [("search", "TCS", 3)]

    assert client.get("/api/v1/stocks/search", params={"q": "   "}).status_code == 422
    assert client.get("/api/v1/stocks/search", params={"q": "TCS", "limit": 0}).status_code == 422
    assert len(fake_provider.calls) == 1


def test_profile_uses_exact_listing_and_returns_404(fake_provider: FakeProvider) -> None:
    client = TestClient(app)
    response = client.get("/api/v1/stocks/NSE/tcs/profile")
    assert response.status_code == 200
    assert response.json()["security"]["symbol"] == "TCS"
    assert response.json()["facts"]["trailing_pe"] == "20.5"
    assert fake_provider.calls[-1] == (
        "profile", SecurityKey(exchange_code="NSE", symbol="TCS")
    )

    fake_provider.profile_available = False
    assert client.get("/api/v1/stocks/NSE/tcs/profile").status_code == 404


def test_prices_validate_range_and_return_bars(fake_provider: FakeProvider) -> None:
    client = TestClient(app)
    url = "/api/v1/stocks/NSE/TCS/prices"
    response = client.get(url, params={"start": "2026-11-05", "end": "2026-11-06"})
    assert response.status_code == 200
    assert response.json()["bars"][0]["close"] == "103"
    assert fake_provider.calls[-1] == (
        "prices", SecurityKey(exchange_code="NSE", symbol="TCS"),
        date(2026, 11, 5), date(2026, 11, 6),
    )

    assert client.get(url, params={"start": "2026-11-06", "end": "2026-11-05"}).status_code == 422
    assert client.get("/api/v1/stocks/NYSE/TCS/prices", params={"start": "2026-11-05", "end": "2026-11-06"}).status_code == 422
    assert len(fake_provider.calls) == 1


def test_provider_failure_is_a_sanitized_502(fake_provider: FakeProvider) -> None:
    fake_provider.fail = True
    response = TestClient(app).get("/api/v1/stocks/search", params={"q": "TCS"})
    assert response.status_code == 502
    assert response.json() == {"detail": "Market data provider request failed"}
