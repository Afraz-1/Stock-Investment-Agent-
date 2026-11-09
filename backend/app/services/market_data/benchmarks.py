"""Cached daily values for two Indian market benchmarks from Yahoo Finance."""

from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from threading import Lock
from time import monotonic
from typing import Any, Callable, Literal

import yfinance as yf
from pydantic import AwareDatetime, BaseModel, Field


_BENCHMARKS = (
    ("NIFTY 50", "^NSEI"),
    ("SENSEX", "^BSESN"),
)
_TWO_PLACES = Decimal("0.01")


class MarketBenchmark(BaseModel):
    """A daily index value, or an explicit unavailable result."""

    name: str
    symbol: str
    status: Literal["available", "unavailable"]
    as_of_day: date | None = None
    value: Decimal | None = Field(default=None, gt=0)
    previous_value: Decimal | None = Field(default=None, gt=0)
    change_points: Decimal | None = None
    change_percent: Decimal | None = None
    source_url: str


class MarketBenchmarks(BaseModel):
    """Both benchmark slots and the time this response was retrieved."""

    retrieved_at: AwareDatetime
    benchmarks: list[MarketBenchmark]


def _close(value: Any) -> Decimal:
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("Invalid benchmark value") from exc
    if not number.is_finite() or number <= 0:
        raise ValueError("Invalid benchmark value")
    return number.quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)


class YahooMarketBenchmarksProvider:
    """Fetch daily index bars and cache the two-card response for five minutes."""

    def __init__(
        self,
        history: Callable[[str], Any] | None = None,
        ttl_seconds: int = 300,
        timer: Callable[[], float] = monotonic,
    ) -> None:
        self._history = history or self._yahoo_history
        self._ttl_seconds = ttl_seconds
        self._timer = timer
        self._lock = Lock()
        self._cached: MarketBenchmarks | None = None
        self._expires_at = 0.0

    @staticmethod
    def _yahoo_history(symbol: str) -> Any:
        return yf.Ticker(symbol).history(period="1mo", interval="1d", auto_adjust=False)

    def get_benchmarks(self) -> MarketBenchmarks:
        with self._lock:
            if self._cached is not None and self._timer() < self._expires_at:
                return self._cached
            result = MarketBenchmarks(
                retrieved_at=datetime.now(timezone.utc),
                benchmarks=[self._read_one(name, symbol) for name, symbol in _BENCHMARKS],
            )
            self._cached = result
            self._expires_at = self._timer() + self._ttl_seconds
            return result

    def _read_one(self, name: str, symbol: str) -> MarketBenchmark:
        source_url = f"https://finance.yahoo.com/quote/{symbol}/"
        unavailable = MarketBenchmark(
            name=name, symbol=symbol, status="unavailable", source_url=source_url
        )
        try:
            bars = self._history(symbol)
            if bars is None or len(bars) < 2 or "Close" not in bars:
                return unavailable
            latest = bars.iloc[-1]
            previous = bars.iloc[-2]
            value = _close(latest["Close"])
            previous_value = _close(previous["Close"])
            trading_day = bars.index[-1].date()
            change = value - previous_value
            return MarketBenchmark(
                name=name,
                symbol=symbol,
                status="available",
                as_of_day=trading_day,
                value=value,
                previous_value=previous_value,
                change_points=change,
                change_percent=(change / previous_value * 100).quantize(
                    _TWO_PLACES, rounding=ROUND_HALF_UP
                ),
                source_url=source_url,
            )
        except Exception:
            # The other index remains usable if Yahoo fails for this symbol.
            return unavailable
