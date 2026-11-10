"""Normalize annual Yahoo statement rows without inventing accounting metadata."""

from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from threading import Lock
from time import monotonic
from typing import Any, Callable, Literal

import yfinance as yf
from pydantic import BaseModel, Field
from yfinance.exceptions import YFTickerMissingError

from app.services.market_data.provider import MarketDataError
from app.services.market_data.schemas import MarketDataSource, SecurityKey
from app.services.market_data.yahoo import _yahoo_symbol


class AnnualFinancialPeriod(BaseModel):
    period_start: date | None = None
    period_end: date
    frequency: Literal["annual"] = "annual"
    accounting_basis: Literal["unknown"] = "unknown"
    original_unit_scale: Literal["ones"] = "ones"
    revenue: Decimal | None = Field(default=None, allow_inf_nan=False)
    operating_income: Decimal | None = Field(default=None, allow_inf_nan=False)
    net_income: Decimal | None = Field(default=None, allow_inf_nan=False)
    operating_cash_flow: Decimal | None = Field(default=None, allow_inf_nan=False)
    capital_expenditure: Decimal | None = Field(default=None, allow_inf_nan=False)


class AnnualFinancialStatements(BaseModel):
    security: SecurityKey
    currency_code: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    sector: str | None = None
    periods: list[AnnualFinancialPeriod] = Field(default_factory=list)
    unavailable_reason: Literal["no_data", "currency_unknown"] | None = None
    source: MarketDataSource


def _amount(value: Any) -> Decimal | None:
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return number if number.is_finite() else None


def _row(frame: Any, name: str, column: Any) -> Decimal | None:
    if frame is None or frame.empty or name not in frame.index or column not in frame.columns:
        return None
    return _amount(frame.at[name, column])


class YahooAnnualFinancialsProvider:
    """Read exact NSE/BSE listings, with a bounded 15-minute response cache."""

    def __init__(
        self,
        ticker_factory: Callable[[str], Any] = yf.Ticker,
        timer: Callable[[], float] = monotonic,
        ttl_seconds: int = 900,
    ) -> None:
        self._ticker_factory = ticker_factory
        self._timer = timer
        self._ttl_seconds = ttl_seconds
        self._cache: dict[SecurityKey, tuple[float, AnnualFinancialStatements]] = {}
        self._lock = Lock()

    def get_annual(self, security: SecurityKey) -> AnnualFinancialStatements | None:
        with self._lock:
            cached = self._cache.get(security)
            if cached and self._timer() < cached[0]:
                return cached[1]
            result = self._fetch(security)
            if result is not None:
                if len(self._cache) >= 128:
                    self._cache.pop(next(iter(self._cache)))
                self._cache[security] = (self._timer() + self._ttl_seconds, result)
            return result

    def _fetch(self, security: SecurityKey) -> AnnualFinancialStatements | None:
        symbol = _yahoo_symbol(security)
        try:
            ticker = self._ticker_factory(symbol)
            info = ticker.info
            if not info or not info.get("symbol"):
                return None
            if info["symbol"].upper() != symbol:
                raise MarketDataError("Yahoo returned a different listing")
            if info.get("quoteType") != "EQUITY":
                return None
            source = MarketDataSource(
                provider="yahoo_finance",
                retrieved_at=datetime.now(timezone.utc),
                url=f"https://finance.yahoo.com/quote/{symbol}/financials/",
            )
            currency = info.get("financialCurrency")
            if not isinstance(currency, str) or len(currency) != 3 or not currency.isalpha():
                return AnnualFinancialStatements(
                    security=security,
                    sector=info.get("sector"),
                    unavailable_reason="currency_unknown",
                    source=source,
                )
            income = ticker.get_income_stmt(freq="yearly")
            cash = ticker.get_cashflow(freq="yearly")
            columns = set()
            for frame in (income, cash):
                if frame is not None and not frame.empty:
                    columns.update(frame.columns)
            periods = []
            for column in sorted(columns, reverse=True)[:4]:
                period_end = column.date() if hasattr(column, "date") else date.fromisoformat(str(column)[:10])
                periods.append(
                    AnnualFinancialPeriod(
                        period_end=period_end,
                        revenue=_row(income, "TotalRevenue", column),
                        operating_income=_row(income, "OperatingIncome", column),
                        net_income=_row(income, "NetIncome", column),
                        operating_cash_flow=_row(cash, "OperatingCashFlow", column),
                        capital_expenditure=_row(cash, "CapitalExpenditure", column),
                    )
                )
            return AnnualFinancialStatements(
                security=security,
                currency_code=currency.upper(),
                sector=info.get("sector"),
                periods=periods,
                unavailable_reason=None if periods else "no_data",
                source=source,
            )
        except YFTickerMissingError:
            return None
        except MarketDataError:
            raise
        except Exception as exc:
            raise MarketDataError("Yahoo annual financials request failed") from exc
