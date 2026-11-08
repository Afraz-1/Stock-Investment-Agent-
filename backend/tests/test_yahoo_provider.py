"""Offline checks for the Yahoo adapter's mapping and failure behavior."""

from datetime import date
from types import SimpleNamespace

import pandas as pd
import pytest
from yfinance.exceptions import YFTickerMissingError

from app.services.market_data.provider import MarketDataError, MarketDataProvider
from app.services.market_data.schemas import SecurityKey
from app.services.market_data.yahoo import YahooMarketDataProvider


def test_search_keeps_indian_equities_and_exchange_identity(monkeypatch) -> None:
    def fake_search(*args, **kwargs):
        assert args == ("TCS",)
        assert kwargs["news_count"] == 0
        return SimpleNamespace(
            quotes=[
                {"symbol": "TCS.NS", "quoteType": "EQUITY", "longname": "Tata Consultancy Services", "currency": "INR"},
                {"symbol": "TCS.BO", "quoteType": "EQUITY", "shortname": "TCS"},
                {"symbol": "TCS.NS", "quoteType": "EQUITY", "shortname": "Duplicate"},
                {"symbol": "TCS", "quoteType": "EQUITY", "shortname": "Unknown exchange"},
                {"symbol": "TCS.NS", "quoteType": "ETF", "shortname": "Fund"},
            ]
        )

    monkeypatch.setattr("app.services.market_data.yahoo.yf.Search", fake_search)
    provider = YahooMarketDataProvider()
    assert isinstance(provider, MarketDataProvider)
    results = provider.search(" TCS ", 10)
    assert [result.security.exchange_code for result in results] == ["NSE", "BSE"]
    assert results[0].company_name == "Tata Consultancy Services"
    assert results[0].source.provider == "yahoo_finance"


def test_profile_requires_exact_listing(monkeypatch) -> None:
    def fake_ticker(symbol):
        assert symbol == "TCS.NS"
        return SimpleNamespace(
            info={
                "symbol": symbol,
                "quoteType": "EQUITY",
                "longName": "Tata Consultancy Services",
                "country": "India",
                "currency": "INR",
                "sector": "Technology",
            }
        )

    monkeypatch.setattr("app.services.market_data.yahoo.yf.Ticker", fake_ticker)
    profile = YahooMarketDataProvider().get_profile(SecurityKey(exchange_code="NSE", symbol="TCS"))
    assert profile is not None
    assert profile.security.symbol == "TCS"
    assert profile.country_code == "IN"
    assert profile.sector == "Technology"


def test_profile_rejects_different_listing(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.market_data.yahoo.yf.Ticker",
        lambda symbol: SimpleNamespace(info={"symbol": "TCS.BO", "quoteType": "EQUITY"}),
    )
    with pytest.raises(MarketDataError, match="different listing"):
        YahooMarketDataProvider().get_profile(SecurityKey(exchange_code="NSE", symbol="TCS"))


def test_missing_listing_returns_none(monkeypatch) -> None:
    def missing_ticker(symbol):
        raise YFTickerMissingError(symbol, "no listing found")

    monkeypatch.setattr("app.services.market_data.yahoo.yf.Ticker", missing_ticker)
    key = SecurityKey(exchange_code="NSE", symbol="UNKNOWN")
    assert YahooMarketDataProvider().get_profile(key) is None
    history = YahooMarketDataProvider().get_prices(key, date(2026, 11, 5), date(2026, 11, 6))
    assert history.unavailable_reason == "no_data"


def test_prices_include_end_date_and_normalize_bars(monkeypatch) -> None:
    frame = pd.DataFrame(
        {"Open": [100.0, 102.0], "High": [105.0, 106.0], "Low": [99.0, 101.0], "Close": [103.0, 104.0], "Volume": [1000, 1100]},
        index=pd.to_datetime(["2026-11-05", "2026-11-06"]).tz_localize("Asia/Kolkata"),
    )

    def fake_ticker(symbol):
        assert symbol == "TCS.NS"

        def history(**kwargs):
            assert kwargs["start"] == "2026-11-05"
            assert kwargs["end"] == "2026-11-07"
            assert kwargs["auto_adjust"] is True
            assert kwargs["raise_errors"] is True
            return frame

        return SimpleNamespace(history=history)

    monkeypatch.setattr("app.services.market_data.yahoo.yf.Ticker", fake_ticker)
    result = YahooMarketDataProvider().get_prices(
        SecurityKey(exchange_code="NSE", symbol="TCS"), date(2026, 11, 5), date(2026, 11, 6)
    )
    assert [bar.trading_day for bar in result.bars] == [date(2026, 11, 5), date(2026, 11, 6)]
    assert result.bars[0].close == 103
    assert result.adjustment == "dividend_adjusted"
    assert result.currency_code == "INR"


def test_empty_prices_and_provider_failure_are_different(monkeypatch) -> None:
    key = SecurityKey(exchange_code="NSE", symbol="TCS")
    monkeypatch.setattr(
        "app.services.market_data.yahoo.yf.Ticker",
        lambda symbol: SimpleNamespace(history=lambda **kwargs: pd.DataFrame()),
    )
    result = YahooMarketDataProvider().get_prices(key, date(2026, 11, 7), date(2026, 11, 8))
    assert result.unavailable_reason == "no_data"

    def failed_ticker(symbol):
        raise ConnectionError("provider unavailable")

    monkeypatch.setattr("app.services.market_data.yahoo.yf.Ticker", failed_ticker)
    with pytest.raises(MarketDataError, match="request failed"):
        YahooMarketDataProvider().get_prices(key, date(2026, 11, 7), date(2026, 11, 8))


def test_invalid_price_bar_is_not_silently_used(monkeypatch) -> None:
    frame = pd.DataFrame(
        {"Open": [110.0], "High": [105.0], "Low": [99.0], "Close": [103.0], "Volume": [1000]},
        index=pd.to_datetime(["2026-11-06"]),
    )
    monkeypatch.setattr(
        "app.services.market_data.yahoo.yf.Ticker",
        lambda symbol: SimpleNamespace(history=lambda **kwargs: frame),
    )
    with pytest.raises(MarketDataError, match="invalid data"):
        YahooMarketDataProvider().get_prices(
            SecurityKey(exchange_code="NSE", symbol="TCS"), date(2026, 11, 6), date(2026, 11, 6)
        )
