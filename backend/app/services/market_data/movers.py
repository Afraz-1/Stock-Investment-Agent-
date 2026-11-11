"""A bounded, cached Yahoo screen of NSE daily market movers."""

from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from threading import Lock
from time import monotonic
from typing import Any, Callable
from zoneinfo import ZoneInfo

import yfinance as yf
from pydantic import AwareDatetime, BaseModel, Field

from app.services.market_data.provider import MarketDataError
from app.services.market_data.schemas import SecurityKey

MIN_MARKET_CAP_INR = 100_000_000_000  # ₹10,000 crore
MIN_DAY_VOLUME = 100_000
SCREEN_PAGE_SIZE = 30
_INDIA = ZoneInfo("Asia/Kolkata")


class MarketMover(BaseModel):
    """One Yahoo NSE equity quote, with its own timestamp and source link."""

    security: SecurityKey
    company_name: str = Field(min_length=1)
    price: Decimal = Field(gt=0)
    previous_close: Decimal = Field(gt=0)
    change_percent: Decimal
    volume: int = Field(ge=0)
    market_cap_inr: int = Field(ge=0)
    quote_at: AwareDatetime
    source_url: str


class MarketMovers(BaseModel):
    """Top positive and negative moves in a declared, filtered NSE universe."""

    as_of_day: date
    latest_quote_at: AwareDatetime
    retrieved_at: AwareDatetime
    min_market_cap_inr: int
    min_day_volume: int
    gainers: list[MarketMover]
    losers: list[MarketMover]
    candidates: list[MarketMover]
    source_url: str = "https://finance.yahoo.com/screener/"


def _decimal(value: Any) -> Decimal | None:
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return number if number.is_finite() else None


def _mover(quote: dict[str, Any]) -> MarketMover | None:
    """Discard incomplete, non-NSE, or out-of-universe Yahoo quotes."""

    symbol = quote.get("symbol")
    if (
        not isinstance(symbol, str)
        or not symbol.endswith(".NS")
        or quote.get("quoteType") != "EQUITY"
        or quote.get("exchange") != "NSI"
        or quote.get("currency") != "INR"
    ):
        return None
    name = quote.get("longName") or quote.get("shortName")
    price = _decimal(quote.get("regularMarketPrice"))
    previous = _decimal(quote.get("regularMarketPreviousClose"))
    change = _decimal(quote.get("regularMarketChangePercent"))
    volume = quote.get("regularMarketVolume")
    market_cap = quote.get("marketCap")
    quote_time = quote.get("regularMarketTime")
    if (
        not isinstance(name, str)
        or not name.strip()
        or price is None
        or price <= 0
        or previous is None
        or previous <= 0
        or change is None
        or not isinstance(volume, int)
        or volume < MIN_DAY_VOLUME
        or not isinstance(market_cap, int)
        or market_cap < MIN_MARKET_CAP_INR
        or not isinstance(quote_time, int)
        or quote_time <= 0
    ):
        return None
    return MarketMover(
        security=SecurityKey(exchange_code="NSE", symbol=symbol[:-3]),
        company_name=name.strip(),
        price=price,
        previous_close=previous,
        change_percent=change,
        volume=volume,
        market_cap_inr=market_cap,
        quote_at=datetime.fromtimestamp(quote_time, tz=timezone.utc),
        source_url=f"https://finance.yahoo.com/quote/{symbol}/",
    )


class YahooMarketMoversProvider:
    """Screen two directions and reuse the result briefly to limit Yahoo calls."""

    def __init__(
        self,
        screen: Callable[..., dict[str, Any]] | None = None,
        ttl_seconds: int = 300,
        timer: Callable[[], float] = monotonic,
    ) -> None:
        self._screen = screen or yf.screen
        self._ttl_seconds = ttl_seconds
        self._timer = timer
        self._lock = Lock()
        self._cached: MarketMovers | None = None
        self._expires_at = 0.0

    def get_movers(self) -> MarketMovers:
        with self._lock:
            if self._cached is not None and self._timer() < self._expires_at:
                return self._cached
            result = self._fetch()
            self._cached = result
            self._expires_at = self._timer() + self._ttl_seconds
            return result

    def _fetch(self) -> MarketMovers:
        query = yf.EquityQuery(
            "and",
            [
                yf.EquityQuery("eq", ["region", "in"]),
                yf.EquityQuery("eq", ["exchange", "NSI"]),
                yf.EquityQuery("gte", ["intradaymarketcap", MIN_MARKET_CAP_INR]),
                yf.EquityQuery("gte", ["dayvolume", MIN_DAY_VOLUME]),
            ],
        )
        try:
            rising = self._screen(
                query, size=SCREEN_PAGE_SIZE, sortField="percentchange", sortAsc=False
            )
            falling = self._screen(
                query, size=SCREEN_PAGE_SIZE, sortField="percentchange", sortAsc=True
            )
            if not isinstance(rising, dict) or not isinstance(falling, dict):
                raise ValueError("Yahoo screener returned an invalid response")
            quotes = [*rising.get("quotes", []), *falling.get("quotes", [])]
            by_symbol: dict[str, MarketMover] = {}
            for quote in quotes:
                if not isinstance(quote, dict):
                    continue
                mover = _mover(quote)
                if mover is None:
                    continue
                symbol = mover.security.symbol
                if symbol not in by_symbol or mover.quote_at > by_symbol[symbol].quote_at:
                    by_symbol[symbol] = mover
            if not by_symbol:
                raise ValueError("Yahoo screener has no usable NSE quotes")
            latest = max(mover.quote_at for mover in by_symbol.values())
            trading_day = latest.astimezone(_INDIA).date()
            current = [
                mover for mover in by_symbol.values()
                if mover.quote_at.astimezone(_INDIA).date() == trading_day
            ]
            gainers = sorted(
                (m for m in current if m.change_percent > 0),
                key=lambda m: m.change_percent,
                reverse=True,
            )[:5]
            losers = sorted(
                (m for m in current if m.change_percent < 0),
                key=lambda m: m.change_percent,
            )[:5]
            return MarketMovers(
                as_of_day=trading_day,
                latest_quote_at=latest,
                retrieved_at=datetime.now(timezone.utc),
                min_market_cap_inr=MIN_MARKET_CAP_INR,
                min_day_volume=MIN_DAY_VOLUME,
                gainers=gainers,
                losers=losers,
                candidates=sorted(current, key=lambda m: (m.market_cap_inr, m.change_percent), reverse=True),
            )
        except Exception as exc:
            raise MarketDataError("Yahoo market movers request failed") from exc
