"""Read-only market overview routes."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.services.market_data.movers import MarketMovers, YahooMarketMoversProvider

router = APIRouter(prefix="/api/v1/market", tags=["market"])
_provider = YahooMarketMoversProvider()


def get_market_movers_provider() -> YahooMarketMoversProvider:
    return _provider


@router.get("/movers", response_model=MarketMovers)
def market_movers(
    provider: Annotated[YahooMarketMoversProvider, Depends(get_market_movers_provider)],
) -> MarketMovers:
    """Return timestamped NSE gainers and losers from a declared universe."""

    return provider.get_movers()
