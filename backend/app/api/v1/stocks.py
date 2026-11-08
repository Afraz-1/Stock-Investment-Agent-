"""Read-only stock research endpoints backed by a market-data provider."""

from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query

from app.services.market_data.provider import MarketDataProvider
from app.services.market_data.schemas import (
    CompanyProfile,
    PriceHistory,
    SecurityKey,
    SecuritySearchResult,
)
from app.services.market_data.yahoo import YahooMarketDataProvider

router = APIRouter(prefix="/api/v1/stocks", tags=["stocks"])

ExchangeCode = Literal["NSE", "BSE"]
StockSymbol = Annotated[
    str, Path(min_length=1, max_length=32, pattern=r"^[A-Za-z0-9][A-Za-z0-9&_.-]*$")
]


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
