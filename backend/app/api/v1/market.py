"""Read-only market overview routes."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.services.market_data.benchmarks import (
    MarketBenchmarks,
    YahooMarketBenchmarksProvider,
)
from app.services.market_data.movers import MarketMovers, YahooMarketMoversProvider

router = APIRouter(prefix="/api/v1/market", tags=["market"])
_provider = YahooMarketMoversProvider()
_benchmarks_provider = YahooMarketBenchmarksProvider()


def get_market_movers_provider() -> YahooMarketMoversProvider:
    return _provider


def get_market_benchmarks_provider() -> YahooMarketBenchmarksProvider:
    return _benchmarks_provider


@router.get("/benchmarks", response_model=MarketBenchmarks)
def market_benchmarks(
    provider: Annotated[YahooMarketBenchmarksProvider, Depends(get_market_benchmarks_provider)],
) -> MarketBenchmarks:
    """Return the latest available Yahoo daily values for NIFTY 50 and SENSEX."""

    return provider.get_benchmarks()


@router.get("/movers", response_model=MarketMovers)
def market_movers(
    provider: Annotated[YahooMarketMoversProvider, Depends(get_market_movers_provider)],
) -> MarketMovers:
    """Return timestamped NSE gainers and losers from a declared universe."""

    return provider.get_movers()
