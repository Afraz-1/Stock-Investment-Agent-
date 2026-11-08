"""Validation tests for normalized provider results."""

from datetime import date, datetime, timezone
from decimal import Decimal

from pydantic import ValidationError
from pytest import raises

from app.services.market_data.schemas import (
    MarketDataSource,
    PriceBar,
    PriceHistory,
    SecurityKey,
)


def test_security_key_requires_exchange_and_symbol() -> None:
    with raises(ValidationError):
        SecurityKey(symbol="TCS")

    with raises(ValidationError):
        SecurityKey(exchange_code="NSE", symbol="   ")

    assert SecurityKey(exchange_code="NSE", symbol="TCS") != SecurityKey(
        exchange_code="BSE", symbol="TCS"
    )


def test_source_requires_timezone_aware_retrieval_time() -> None:
    with raises(ValidationError):
        MarketDataSource(provider="example", retrieved_at=datetime(2026, 11, 8))

    source = MarketDataSource(
        provider="example", retrieved_at=datetime(2026, 11, 8, tzinfo=timezone.utc)
    )
    assert source.published_at is None


def test_price_bar_rejects_invalid_ohlcv() -> None:
    with raises(ValidationError):
        PriceBar(
            trading_day=date(2026, 11, 6),
            open=Decimal("101"),
            high=Decimal("100"),
            low=Decimal("95"),
            close=Decimal("98"),
            volume=10,
        )

    with raises(ValidationError):
        PriceBar(
            trading_day=date(2026, 11, 6),
            open=Decimal("98"),
            high=Decimal("100"),
            low=Decimal("95"),
            close=Decimal("99"),
            volume=-1,
        )


def test_price_history_requires_reason_or_ordered_bars() -> None:
    security = SecurityKey(exchange_code="NSE", symbol="EXAMPLE")
    source = MarketDataSource(
        provider="example", retrieved_at=datetime(2026, 11, 8, tzinfo=timezone.utc)
    )
    first = PriceBar(
        trading_day=date(2026, 11, 5),
        open=Decimal("98"),
        high=Decimal("100"),
        low=Decimal("95"),
        close=Decimal("99"),
        volume=10,
    )
    second = first.model_copy(update={"trading_day": date(2026, 11, 6)})

    with raises(ValidationError):
        PriceHistory(security=security, adjustment="unknown", source=source)

    with raises(ValidationError):
        PriceHistory(
            security=security,
            currency_code="INR",
            adjustment="raw",
            bars=[second, first],
            source=source,
        )

    history = PriceHistory(
        security=security,
        currency_code="INR",
        adjustment="raw",
        bars=[first, second],
        source=source,
    )
    assert len(history.bars) == 2

    unavailable = PriceHistory(
        security=security,
        adjustment="unknown",
        unavailable_reason="no_data",
        source=source,
    )
    assert unavailable.bars == []
