"""Provider-independent shapes for market data results."""

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, HttpUrl, model_validator


class SecurityKey(BaseModel):
    """Identify a listing by both exchange and symbol."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    exchange_code: str = Field(min_length=1, max_length=16)
    symbol: str = Field(min_length=1, max_length=32)


class MarketDataSource(BaseModel):
    """Provenance and freshness of one provider result."""

    model_config = ConfigDict(str_strip_whitespace=True)

    provider: str = Field(min_length=1)
    retrieved_at: AwareDatetime
    published_at: AwareDatetime | None = None
    url: HttpUrl | None = None


class SecuritySearchResult(BaseModel):
    """One possible exchange listing returned by search."""

    model_config = ConfigDict(str_strip_whitespace=True)

    security: SecurityKey
    company_name: str = Field(min_length=1)
    isin: str | None = None
    currency_code: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    source: MarketDataSource


class CompanyProfile(BaseModel):
    """Company facts available from a provider for one listing."""

    model_config = ConfigDict(str_strip_whitespace=True)

    security: SecurityKey
    company_name: str = Field(min_length=1)
    country_code: str | None = Field(default=None, pattern=r"^[A-Z]{2}$")
    sector: str | None = None
    industry: str | None = None
    description: str | None = None
    isin: str | None = None
    currency_code: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    source: MarketDataSource


class PriceBar(BaseModel):
    """One trading day's normalized OHLCV observations."""

    trading_day: date
    open: Decimal = Field(gt=0, allow_inf_nan=False)
    high: Decimal = Field(gt=0, allow_inf_nan=False)
    low: Decimal = Field(gt=0, allow_inf_nan=False)
    close: Decimal = Field(gt=0, allow_inf_nan=False)
    volume: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_range(self) -> "PriceBar":
        """Reject price observations outside the day's low and high."""

        if self.low > self.high:
            raise ValueError("low cannot exceed high")
        if not self.low <= self.open <= self.high:
            raise ValueError("open must be between low and high")
        if not self.low <= self.close <= self.high:
            raise ValueError("close must be between low and high")
        return self


class PriceHistory(BaseModel):
    """A price series with an explicit adjustment basis and source."""

    security: SecurityKey
    currency_code: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    adjustment: Literal["raw", "split_adjusted", "dividend_adjusted", "unknown"]
    bars: list[PriceBar] = Field(default_factory=list)
    unavailable_reason: Literal["no_data", "unsupported"] | None = None
    warnings: list[str] = Field(default_factory=list)
    source: MarketDataSource

    @model_validator(mode="after")
    def validate_history(self) -> "PriceHistory":
        """Require complete, ordered bars or an explicit empty-result reason."""

        if not self.bars:
            if self.unavailable_reason is None:
                raise ValueError("empty history requires an unavailable reason")
            return self

        if self.unavailable_reason is not None:
            raise ValueError("history with bars cannot have an unavailable reason")
        if self.currency_code is None:
            raise ValueError("history with bars requires a currency code")

        days = [bar.trading_day for bar in self.bars]
        if days != sorted(set(days)):
            raise ValueError("price bars must have unique, ascending trading days")
        return self


class StoredPriceHistory(BaseModel):
    """A database snapshot for one provider and adjustment basis."""

    security: SecurityKey
    currency_code: str = Field(pattern=r"^[A-Z]{3}$")
    provider: str = Field(min_length=1)
    adjustment: Literal["raw", "split_adjusted", "dividend_adjusted", "unknown"]
    bars: list[PriceBar]
    oldest_retrieved_at: AwareDatetime | None = None
    newest_retrieved_at: AwareDatetime | None = None
    unavailable_reason: Literal["no_data"] | None = None
