"""Daily benchmark values must be sourced, dated, and safe when unavailable."""

from decimal import Decimal

import pandas as pd
from fastapi.testclient import TestClient

from app.api.v1.market import get_market_benchmarks_provider
from app.main import app
from app.services.market_data.benchmarks import YahooMarketBenchmarksProvider


def bars(previous: float, latest: float) -> pd.DataFrame:
    return pd.DataFrame(
        {"Close": [previous, latest]},
        index=pd.to_datetime(["2026-11-06", "2026-11-09"], utc=True),
    )


def test_calculates_day_change_and_caches_result() -> None:
    calls: list[str] = []
    clock = [0.0]

    def history(symbol: str) -> pd.DataFrame:
        calls.append(symbol)
        return bars(25000, 25125) if symbol == "^NSEI" else bars(81000, 80600)

    provider = YahooMarketBenchmarksProvider(
        history=history, ttl_seconds=300, timer=lambda: clock[0]
    )
    result = provider.get_benchmarks()
    nifty, sensex = result.benchmarks
    assert calls == ["^NSEI", "^BSESN"]
    assert result.retrieved_at.tzinfo is not None
    assert nifty.status == "available"
    assert nifty.as_of_day.isoformat() == "2026-11-09"
    assert nifty.value == 25125
    assert nifty.previous_value == 25000
    assert nifty.change_points == 125
    assert nifty.change_percent == Decimal("0.50")
    assert sensex.change_points == -400
    assert sensex.change_percent == Decimal("-0.49")
    assert provider.get_benchmarks() is result
    assert len(calls) == 2
    clock[0] = 301
    provider.get_benchmarks()
    assert len(calls) == 4


def test_missing_or_failed_symbol_does_not_fabricate_values() -> None:
    def history(symbol: str) -> pd.DataFrame:
        if symbol == "^NSEI":
            return bars(25000, float("nan"))
        raise RuntimeError("provider unavailable")

    result = YahooMarketBenchmarksProvider(history=history).get_benchmarks()
    assert [item.status for item in result.benchmarks] == ["unavailable", "unavailable"]
    assert all(item.value is None and item.as_of_day is None for item in result.benchmarks)


def test_route_exposes_daily_values_and_source() -> None:
    provider = YahooMarketBenchmarksProvider(
        history=lambda symbol: bars(25000, 25125)
    )
    app.dependency_overrides[get_market_benchmarks_provider] = lambda: provider
    try:
        response = TestClient(app).get("/api/v1/market/benchmarks")
        assert response.status_code == 200
        data = response.json()
        assert len(data["benchmarks"]) == 2
        assert data["benchmarks"][0]["symbol"] == "^NSEI"
        assert data["benchmarks"][0]["change_percent"] == "0.50"
        assert data["benchmarks"][0]["source_url"].endswith("/^NSEI/")
    finally:
        app.dependency_overrides.pop(get_market_benchmarks_provider, None)
