"""Read-only stock research endpoints backed by a market-data provider."""

from datetime import date, datetime, timezone
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import DailyPrice, Exchange, Security
from app.services.market_data.provider import MarketDataProvider
from app.services.market_data.schemas import (
    CompanyProfile,
    PriceBar,
    PriceHistory,
    SecurityKey,
    SecuritySearchResult,
    StoredPriceHistory,
)
from app.services.market_data.yahoo import YahooMarketDataProvider

router = APIRouter(prefix="/api/v1/stocks", tags=["stocks"])

ExchangeCode = Literal["NSE", "BSE"]
StockSymbol = Annotated[
    str, Path(min_length=1, max_length=32, pattern=r"^[A-Za-z0-9][A-Za-z0-9&_.-]*$")
]


def _as_aware_utc(value: datetime) -> datetime:
    """SQLite drops UTC timezone information in offline tests."""

    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def get_market_data_provider() -> MarketDataProvider:
    """Supply the provider; tests can replace this dependency without network calls."""

    return YahooMarketDataProvider()


@router.get("/search", response_model=list[SecuritySearchResult])
def search_stocks(
    q: Annotated[str, Query(min_length=1, max_length=100)],
    provider: Annotated[MarketDataProvider, Depends(get_market_data_provider)],
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> list[SecuritySearchResult]:
    """Find NSE and BSE equity listings by name or symbol."""

    query = q.strip()
    if not query:
        raise HTTPException(status_code=422, detail="Search query cannot be blank")
    return provider.search(query, limit)


@router.get("/{exchange}/{symbol}/profile", response_model=CompanyProfile)
def stock_profile(
    exchange: ExchangeCode,
    symbol: StockSymbol,
    provider: Annotated[MarketDataProvider, Depends(get_market_data_provider)],
) -> CompanyProfile:
    """Return a profile for one exact exchange listing."""

    profile = provider.get_profile(SecurityKey(exchange_code=exchange, symbol=symbol.upper()))
    if profile is None:
        raise HTTPException(status_code=404, detail="Stock listing not found")
    return profile


@router.get("/{exchange}/{symbol}/prices", response_model=PriceHistory)
def stock_prices(
    exchange: ExchangeCode,
    symbol: StockSymbol,
    start: Annotated[date, Query(description="First trading date, inclusive")],
    end: Annotated[date, Query(description="Last trading date, inclusive")],
    provider: Annotated[MarketDataProvider, Depends(get_market_data_provider)],
) -> PriceHistory:
    """Return daily prices, with the requested start and end dates inclusive."""

    if start > end or end == date.max:
        raise HTTPException(status_code=422, detail="Invalid price date range")
    return provider.get_prices(
        SecurityKey(exchange_code=exchange, symbol=symbol.upper()), start, end
    )


@router.get(
    "/{exchange}/{symbol}/saved-prices", response_model=StoredPriceHistory
)
def saved_stock_prices(
    exchange: ExchangeCode,
    symbol: StockSymbol,
    start: Annotated[date, Query(description="First trading date, inclusive")],
    end: Annotated[date, Query(description="Last trading date, inclusive")],
    db: Annotated[Session, Depends(get_db)],
) -> StoredPriceHistory:
    """Read the locally saved Yahoo price bars for one exact listing."""

    if start > end:
        raise HTTPException(status_code=422, detail="Invalid price date range")

    key = SecurityKey(exchange_code=exchange, symbol=symbol.upper())
    try:
        security = db.scalar(
            select(Security)
            .join(Exchange, Security.exchange_id == Exchange.id)
            .where(Exchange.code == exchange, Security.symbol == key.symbol)
        )
        if security is None:
            raise HTTPException(status_code=404, detail="Stock listing is not registered")

        rows = db.scalars(
            select(DailyPrice)
            .where(
                DailyPrice.security_id == security.id,
                DailyPrice.provider == "yahoo_finance",
                DailyPrice.adjustment == "dividend_adjusted",
                DailyPrice.trading_day >= start,
                DailyPrice.trading_day <= end,
            )
            .order_by(DailyPrice.trading_day)
        ).all()
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Database unavailable") from exc

    return StoredPriceHistory(
        security=key,
        currency_code=security.currency_code,
        provider="yahoo_finance",
        adjustment="dividend_adjusted",
        bars=[
            PriceBar(
                trading_day=row.trading_day,
                open=row.open,
                high=row.high,
                low=row.low,
                close=row.close,
                volume=row.volume,
            )
            for row in rows
        ],
        oldest_retrieved_at=min(
            (_as_aware_utc(row.source_retrieved_at) for row in rows), default=None
        ),
        newest_retrieved_at=max(
            (_as_aware_utc(row.source_retrieved_at) for row in rows), default=None
        ),
        unavailable_reason=None if rows else "no_data",
    )
