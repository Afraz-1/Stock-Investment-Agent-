"""Interface that all external market-data adapters must implement."""

from abc import ABC, abstractmethod
from datetime import date

from app.services.market_data.schemas import (
    CompanyProfile,
    PriceHistory,
    SecurityKey,
    SecuritySearchResult,
)


class MarketDataError(Exception):
    """The provider failed; an empty result would incorrectly imply no data."""


class MarketDataProvider(ABC):
    """Contract for company search, profiles, and daily price history."""

    @abstractmethod
    def search(self, query: str, limit: int) -> list[SecuritySearchResult]:
        """Return all matching listings, including different exchanges."""

    @abstractmethod
    def get_profile(self, security: SecurityKey) -> CompanyProfile | None:
        """Return a profile or None if this exact listing is unknown."""

    @abstractmethod
    def get_prices(
        self, security: SecurityKey, start_date: date, end_date: date
    ) -> PriceHistory:
        """Return daily prices for an inclusive date range."""
