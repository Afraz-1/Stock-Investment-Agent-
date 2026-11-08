"""Fetch and persist daily prices for a registered exchange listing."""

from datetime import date

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.models import DailyPrice, Exchange, Security
from app.services.market_data.provider import MarketDataProvider
from app.services.market_data.schemas import SecurityKey


class SecurityNotFoundError(LookupError):
    """The requested security ID does not exist in our registry."""


def ingest_daily_prices(
    db: Session,
    provider: MarketDataProvider,
    security_id: int,
    start_date: date,
    end_date: date,
) -> int:
    """Fetch and upsert prices; the caller owns commit or rollback.

    Returns the number of bars received, including existing bars refreshed.
    """

    if start_date > end_date:
        raise ValueError("Start date must not be after end date")

    security = db.get(Security, security_id)
    if security is None:
        raise SecurityNotFoundError(f"Security {security_id} does not exist")
    exchange = db.get(Exchange, security.exchange_id)
    if exchange is None:
        raise SecurityNotFoundError(f"Exchange {security.exchange_id} does not exist")

    key = SecurityKey(exchange_code=exchange.code, symbol=security.symbol)
    history = provider.get_prices(key, start_date, end_date)
    if history.security != key:
        raise ValueError("Provider returned prices for a different listing")
    if not history.bars:
        return 0
    if history.currency_code != security.currency_code:
        raise ValueError("Provider currency differs from the registered listing")
    if any(not start_date <= bar.trading_day <= end_date for bar in history.bars):
        raise ValueError("Provider returned a price outside the requested dates")

    source_url = str(history.source.url) if history.source.url else None
    rows = [
        {
            "security_id": security_id,
            "trading_day": bar.trading_day,
            "provider": history.source.provider,
            "adjustment": history.adjustment,
            "currency_code": history.currency_code,
            "open": bar.open,
            "high": bar.high,
            "low": bar.low,
            "close": bar.close,
            "volume": bar.volume,
            "source_retrieved_at": history.source.retrieved_at,
            "source_url": source_url,
        }
        for bar in history.bars
    ]

    dialect = db.get_bind().dialect.name
    if dialect == "postgresql":
        statement = postgres_insert(DailyPrice)
    elif dialect == "sqlite":
        statement = sqlite_insert(DailyPrice)
    else:
        raise RuntimeError(f"Price ingestion does not support {dialect}")

    excluded = statement.excluded
    statement = statement.on_conflict_do_update(
        index_elements=["security_id", "trading_day", "provider", "adjustment"],
        set_={
            "currency_code": excluded.currency_code,
            "open": excluded.open,
            "high": excluded.high,
            "low": excluded.low,
            "close": excluded.close,
            "volume": excluded.volume,
            "source_retrieved_at": excluded.source_retrieved_at,
            "source_url": excluded.source_url,
            # SQLAlchemy's Python-side onupdate is not called by an upsert.
            "updated_at": func.now(),
        },
        where=DailyPrice.source_retrieved_at <= excluded.source_retrieved_at,
    )
    db.execute(statement, rows)
    return len(rows)
