"""Offline tests for fetching and saving registered listings' daily bars."""

from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import Mock

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.models import Base, Company, DailyPrice, Exchange, Security
from app.services.market_data.ingestion import SecurityNotFoundError, ingest_daily_prices
from app.services.market_data.provider import MarketDataError, MarketDataProvider
from app.services.market_data.schemas import (
    MarketDataSource,
    PriceBar,
    PriceHistory,
    SecurityKey,
)


@pytest.fixture
def db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(Company(id=1, legal_name="Example Limited", country_code="IN"))
        session.add(
            Exchange(
                id=1, code="NSE", name="National Stock Exchange",
                country_code="IN", timezone_name="Asia/Kolkata",
            )
        )
        session.flush()
        session.add(
            Security(
                id=1, company_id=1, exchange_id=1,
                symbol="EXAMPLE", currency_code="INR",
            )
        )
        session.commit()
        yield session
    engine.dispose()


def make_history(
    *, close: str = "103", retrieved_day: int = 8,
    key: SecurityKey | None = None, currency: str = "INR",
    trading_day: date = date(2026, 11, 6),
) -> PriceHistory:
    return PriceHistory(
        security=key or SecurityKey(exchange_code="NSE", symbol="EXAMPLE"),
        currency_code=currency,
        adjustment="dividend_adjusted",
        bars=[
            PriceBar(
                trading_day=trading_day,
                open=Decimal("100"), high=Decimal("105"), low=Decimal("99"),
                close=Decimal(close), volume=1000,
            )
        ],
        source=MarketDataSource(
            provider="yahoo_finance",
            retrieved_at=datetime(2026, 11, retrieved_day, tzinfo=timezone.utc),
            url="https://finance.yahoo.com/quote/EXAMPLE.NS/",
        ),
    )


def provider_returning(history: PriceHistory) -> Mock:
    provider = Mock(spec=MarketDataProvider)
    provider.get_prices.return_value = history
    return provider


def test_ingestion_saves_and_refreshes_without_duplicates(db: Session) -> None:
    provider = provider_returning(make_history())
    start = end = date(2026, 11, 6)

    assert ingest_daily_prices(db, provider, 1, start, end) == 1
    provider.get_prices.assert_called_once_with(
        SecurityKey(exchange_code="NSE", symbol="EXAMPLE"), start, end
    )
    db.commit()
    assert db.scalar(select(func.count()).select_from(DailyPrice)) == 1
    stored = db.scalar(select(DailyPrice))
    assert stored is not None
    assert stored.close == Decimal("103.00000000")
    assert stored.source_url == "https://finance.yahoo.com/quote/EXAMPLE.NS/"

    provider.get_prices.return_value = make_history(close="104", retrieved_day=9)
    assert ingest_daily_prices(db, provider, 1, start, end) == 1
    db.commit()
    db.expire_all()
    assert db.scalar(select(func.count()).select_from(DailyPrice)) == 1
    assert db.scalar(select(DailyPrice)).close == Decimal("104.00000000")


def test_older_result_does_not_replace_newer_data(db: Session) -> None:
    provider = provider_returning(make_history(close="104", retrieved_day=9))
    day = date(2026, 11, 6)
    ingest_daily_prices(db, provider, 1, day, day)
    db.commit()

    provider.get_prices.return_value = make_history(close="102", retrieved_day=8)
    ingest_daily_prices(db, provider, 1, day, day)
    db.commit()
    db.expire_all()
    assert db.scalar(select(DailyPrice)).close == Decimal("104.00000000")


@pytest.mark.parametrize(
    "history",
    [
        make_history(key=SecurityKey(exchange_code="BSE", symbol="EXAMPLE")),
        make_history(currency="USD"),
        make_history(trading_day=date(2026, 11, 5)),
    ],
)
def test_mismatched_provider_data_is_not_saved(db: Session, history: PriceHistory) -> None:
    provider = provider_returning(history)
    with pytest.raises(ValueError):
        ingest_daily_prices(db, provider, 1, date(2026, 11, 6), date(2026, 11, 6))
    assert db.scalar(select(func.count()).select_from(DailyPrice)) == 0


def test_missing_listing_and_no_data_do_not_create_rows(db: Session) -> None:
    provider = provider_returning(make_history())
    day = date(2026, 11, 6)
    with pytest.raises(SecurityNotFoundError):
        ingest_daily_prices(db, provider, 999, day, day)
    provider.get_prices.assert_not_called()

    provider.get_prices.return_value = PriceHistory(
        security=SecurityKey(exchange_code="NSE", symbol="EXAMPLE"),
        adjustment="unknown",
        unavailable_reason="no_data",
        source=MarketDataSource(
            provider="yahoo_finance",
            retrieved_at=datetime(2026, 11, 8, tzinfo=timezone.utc),
        ),
    )
    assert ingest_daily_prices(db, provider, 1, day, day) == 0
    assert db.scalar(select(func.count()).select_from(DailyPrice)) == 0


def test_provider_failure_and_rollback_leave_no_prices(db: Session) -> None:
    provider = provider_returning(make_history())
    day = date(2026, 11, 6)
    provider.get_prices.side_effect = MarketDataError("Yahoo unavailable")
    with pytest.raises(MarketDataError):
        ingest_daily_prices(db, provider, 1, day, day)
    assert db.scalar(select(func.count()).select_from(DailyPrice)) == 0

    provider.get_prices.side_effect = None
    ingest_daily_prices(db, provider, 1, day, day)
    db.rollback()
    assert db.scalar(select(func.count()).select_from(DailyPrice)) == 0
