"""Market mover ranking must stay sourced, bounded, and date-consistent."""

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.api.v1.market import get_market_movers_provider
from app.main import app
from app.services.market_data.movers import YahooMarketMoversProvider
from app.services.market_data.provider import MarketDataError


def quote(symbol: str, change: float, *, day: int = 9, market_cap: int = 200_000_000_000) -> dict:
    return {
        "symbol": f"{symbol}.NS",
        "quoteType": "EQUITY",
        "exchange": "NSI",
        "currency": "INR",
        "longName": f"{symbol} Limited",
        "regularMarketPrice": 100 + change,
        "regularMarketPreviousClose": 100,
        "regularMarketChangePercent": change,
        "regularMarketVolume": 200_000,
        "marketCap": market_cap,
        "regularMarketTime": int(datetime(2026, 11, day, 9, tzinfo=timezone.utc).timestamp()),
    }


def test_sorts_valid_quotes_and_filters_old_or_out_of_universe() -> None:
    calls = []
    clock = [0.0]

    def screen(query, *, size, sortField, sortAsc):
        calls.append(sortAsc)
        if sortAsc:
            return {"quotes": [quote("DOWN", -4), quote("OLD", -10, day=6), quote("TINY", -8, market_cap=1)]}
        return {"quotes": [quote("UP", 3), quote("MOREUP", 5), quote("DOWN", -4)]}

    provider = YahooMarketMoversProvider(screen=screen, ttl_seconds=300, timer=lambda: clock[0])
    result = provider.get_movers()
    assert result.as_of_day.isoformat() == "2026-11-09"
    assert [m.security.symbol for m in result.gainers] == ["MOREUP", "UP"]
    assert [m.security.symbol for m in result.losers] == ["DOWN"]
    assert result.min_market_cap_inr == 100_000_000_000
    assert calls == [False, True]
    assert provider.get_movers() is result
    assert calls == [False, True]
    clock[0] = 301.0
    provider.get_movers()
    assert calls == [False, True, False, True]


def test_route_exposes_source_and_provider_failures() -> None:
    def screen(query, *, size, sortField, sortAsc):
        return {"quotes": [quote("UP", 3)]}

    provider = YahooMarketMoversProvider(screen=screen)
    app.dependency_overrides[get_market_movers_provider] = lambda: provider
    try:
        response = TestClient(app).get("/api/v1/market/movers")
        assert response.status_code == 200
        data = response.json()
        assert data["gainers"][0]["security"] == {"exchange_code": "NSE", "symbol": "UP"}
        assert data["gainers"][0]["source_url"].endswith("/UP.NS/")
        assert data["losers"] == []
    finally:
        app.dependency_overrides.pop(get_market_movers_provider, None)

    def failed_screen(query, *, size, sortField, sortAsc):
        raise RuntimeError("private provider detail")

    provider = YahooMarketMoversProvider(screen=failed_screen)
    app.dependency_overrides[get_market_movers_provider] = lambda: provider
    try:
        response = TestClient(app).get("/api/v1/market/movers")
        assert response.status_code == 502
        assert response.json() == {"detail": "Market data provider request failed"}
    finally:
        app.dependency_overrides.pop(get_market_movers_provider, None)


def test_empty_provider_result_is_not_fabricated() -> None:
    provider = YahooMarketMoversProvider(
        screen=lambda query, **kwargs: {"quotes": []}
    )
    with pytest.raises(MarketDataError):
        provider.get_movers()
