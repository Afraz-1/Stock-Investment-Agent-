"""Annual statements and metrics stay dated, sourced, and reproducible."""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from yfinance.exceptions import YFTickerMissingError

from app.api.v1.stocks import get_financials_provider
from app.main import app
from app.services.market_data.financials import YahooAnnualFinancialsProvider
from app.services.market_data.fundamentals import calculate_annual_metrics
from app.services.market_data.provider import MarketDataError
from app.services.market_data.schemas import SecurityKey


KEY = SecurityKey(exchange_code="NSE", symbol="TCS")
DATES = pd.to_datetime(["2026-03-31", "2025-03-31"])


def ticker(symbol: str, *, sector: str = "Technology", currency: str | None = "INR"):
    income = pd.DataFrame(
        {DATES[0]: [120.0, 30.0, 18.0], DATES[1]: [100.0, 22.0, 12.0]},
        index=["TotalRevenue", "OperatingIncome", "NetIncome"],
    )
    cash = pd.DataFrame(
        {DATES[0]: [25.0, -5.0], DATES[1]: [20.0, -4.0]},
        index=["OperatingCashFlow", "CapitalExpenditure"],
    )
    return SimpleNamespace(
        info={"symbol": symbol, "quoteType": "EQUITY", "financialCurrency": currency, "sector": sector},
        get_income_stmt=lambda **kwargs: income,
        get_cashflow=lambda **kwargs: cash,
    )


def test_normalizes_annual_rows_and_calculates_metrics() -> None:
    calls = []
    clock = [0.0]

    def factory(symbol: str):
        calls.append(symbol)
        return ticker(symbol)

    provider = YahooAnnualFinancialsProvider(ticker_factory=factory, timer=lambda: clock[0])
    statements = provider.get_annual(KEY)
    assert statements is not None
    assert statements.currency_code == "INR"
    assert statements.periods[0].period_end == date(2026, 3, 31)
    assert statements.periods[0].accounting_basis == "unknown"
    assert statements.periods[0].revenue == 120
    assert statements.periods[0].capital_expenditure == -5
    assert statements.source.published_at is None
    assert statements.source.retrieved_at.tzinfo is not None
    assert calls == ["TCS.NS"]
    assert provider.get_annual(KEY) is statements
    clock[0] = 901
    provider.get_annual(KEY)
    assert calls == ["TCS.NS", "TCS.NS"]

    metrics = {item.key: item for item in calculate_annual_metrics(statements)}
    assert {key: item.value for key, item in metrics.items()} == {
        "operating_margin": Decimal("25.00"),
        "net_margin": Decimal("15.00"),
        "revenue_growth": Decimal("20.00"),
        "free_cash_flow": Decimal("20.0"),
    }
    assert metrics["revenue_growth"].formula_version == "1"
    assert [item.period_end for item in metrics["revenue_growth"].inputs] == [
        date(2026, 3, 31), date(2025, 3, 31)
    ]
    assert metrics["free_cash_flow"].unit == "currency"


def test_missing_currency_and_wrong_listing_are_explicit() -> None:
    provider = YahooAnnualFinancialsProvider(ticker_factory=lambda symbol: ticker(symbol, currency=None))
    result = provider.get_annual(KEY)
    assert result is not None
    assert result.unavailable_reason == "currency_unknown"
    assert result.periods == []

    provider = YahooAnnualFinancialsProvider(ticker_factory=lambda symbol: ticker("OTHER.NS"))
    with pytest.raises(MarketDataError, match="different listing"):
        provider.get_annual(KEY)


def test_metrics_mark_unsupported_or_invalid_inputs() -> None:
    financial = YahooAnnualFinancialsProvider(
        ticker_factory=lambda symbol: ticker(symbol, sector="Financial Services")
    ).get_annual(KEY)
    assert financial is not None
    assert all(item.status == "sector_not_supported" for item in calculate_annual_metrics(financial))

    statements = YahooAnnualFinancialsProvider(ticker_factory=ticker).get_annual(KEY)
    assert statements is not None
    statements.periods[0].revenue = Decimal("0")
    statements.periods[0].capital_expenditure = Decimal("5")
    metrics = {item.key: item for item in calculate_annual_metrics(statements)}
    assert metrics["net_margin"].status == "not_meaningful"
    assert metrics["free_cash_flow"].status == "not_meaningful"
    assert metrics["net_margin"].value is None

    statements.periods[0].revenue = Decimal("120")
    statements.periods[1].period_end = date(2023, 3, 31)
    growth = {item.key: item for item in calculate_annual_metrics(statements)}["revenue_growth"]
    assert growth.status == "not_meaningful"
    assert growth.value is None


def test_route_returns_periods_and_metric_inputs() -> None:
    provider = YahooAnnualFinancialsProvider(ticker_factory=ticker)
    app.dependency_overrides[get_financials_provider] = lambda: provider
    try:
        response = TestClient(app).get("/api/v1/stocks/NSE/tcs/annual-financials")
        assert response.status_code == 200
        body = response.json()
        assert body["statements"]["security"] == {"exchange_code": "NSE", "symbol": "TCS"}
        assert body["statements"]["periods"][0]["revenue"] == "120.0"
        assert body["metrics"][0]["inputs"][0]["field"] == "operating_income"
    finally:
        app.dependency_overrides.pop(get_financials_provider, None)


def test_unknown_listing_returns_404() -> None:
    def missing(symbol: str):
        raise YFTickerMissingError(symbol, "missing")

    app.dependency_overrides[get_financials_provider] = lambda: YahooAnnualFinancialsProvider(
        ticker_factory=missing
    )
    try:
        response = TestClient(app).get("/api/v1/stocks/NSE/UNKNOWN/annual-financials")
        assert response.status_code == 404
    finally:
        app.dependency_overrides.pop(get_financials_provider, None)
