"""Personal-use Yahoo Finance adapter for Indian cash equities."""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from math import isnan

import yfinance as yf
from pydantic import ValidationError
from yfinance.exceptions import YFTickerMissingError

from app.services.market_data.provider import MarketDataError, MarketDataProvider
from app.services.market_data.schemas import (
    CompanyProfile,
    CompanyFacts,
    MarketDataSource,
    PriceBar,
    PriceHistory,
    SecurityKey,
    SecuritySearchResult,
)

_SUFFIXES = {"NSE": ".NS", "BSE": ".BO"}


def _yahoo_symbol(security: SecurityKey) -> str:
    """Translate our exchange-aware key to Yahoo's ticker convention."""

    exchange = security.exchange_code.upper()
    if exchange not in _SUFFIXES:
        raise ValueError(f"Yahoo adapter does not support exchange {exchange}")
    return f"{security.symbol.upper()}{_SUFFIXES[exchange]}"


def _security_key(symbol: str) -> SecurityKey | None:
    """Accept only Yahoo symbols that unambiguously identify NSE or BSE."""

    upper = symbol.upper()
    for exchange, suffix in _SUFFIXES.items():
        if upper.endswith(suffix) and len(upper) > len(suffix):
            return SecurityKey(exchange_code=exchange, symbol=upper[: -len(suffix)])
    return None


def _source(symbol: str) -> MarketDataSource:
    return MarketDataSource(
        provider="yahoo_finance",
        retrieved_at=datetime.now(timezone.utc),
        url=f"https://finance.yahoo.com/quote/{symbol}/",
    )


def _positive(value: object) -> Decimal | None:
    """Treat missing, non-finite, and non-meaningful provider metrics as absent."""

    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return number if number.is_finite() and number > 0 else None


def _company_facts(info: dict) -> CompanyFacts:
    low = _positive(info.get("fiftyTwoWeekLow"))
    high = _positive(info.get("fiftyTwoWeekHigh"))
    if low is None or high is None or low > high:
        low = high = None
    return CompanyFacts(
        market_cap=_positive(info.get("marketCap")),
        trailing_pe=_positive(info.get("trailingPE")),
        price_to_book=_positive(info.get("priceToBook")),
        fifty_two_week_low=low,
        fifty_two_week_high=high,
    )


class YahooMarketDataProvider(MarketDataProvider):
    """Normalize yfinance results without exposing its data shapes to the app."""

    def search(self, query: str, limit: int) -> list[SecuritySearchResult]:
        if not query.strip():
            raise ValueError("Search query cannot be empty")
        if not 1 <= limit <= 50:
            raise ValueError("Search limit must be between 1 and 50")

        try:
            quotes = yf.Search(
                query.strip(), max_results=50, news_count=0, lists_count=0, timeout=10
            ).quotes
            results: list[SecuritySearchResult] = []
            seen: set[SecurityKey] = set()
            for quote in quotes:
                if quote.get("quoteType") != "EQUITY":
                    continue
                key = _security_key(quote.get("symbol") or "")
                name = quote.get("longname") or quote.get("shortname")
                if key is None or key in seen or not name:
                    continue
                seen.add(key)
                results.append(
                    SecuritySearchResult(
                        security=key,
                        company_name=name,
                        isin=quote.get("isin"),
                        currency_code=(quote.get("currency") or "INR").upper(),
                        source=_source(_yahoo_symbol(key)),
                    )
                )
                if len(results) == limit:
                    break
            return results
        except (ValidationError, AttributeError, KeyError, TypeError, ValueError) as exc:
            raise MarketDataError("Yahoo search returned invalid data") from exc
        except Exception as exc:
            raise MarketDataError("Yahoo search failed") from exc

    def get_profile(self, security: SecurityKey) -> CompanyProfile | None:
        symbol = _yahoo_symbol(security)
        try:
            info = yf.Ticker(symbol).info
            if not info or not info.get("symbol"):
                return None
            if info["symbol"].upper() != symbol:
                raise MarketDataError("Yahoo returned a different listing")
            if info.get("quoteType") != "EQUITY":
                return None
            name = info.get("longName") or info.get("shortName")
            if not name:
                raise MarketDataError("Yahoo profile is missing company name")
            return CompanyProfile(
                security=security,
                company_name=name,
                country_code="IN",
                sector=info.get("sector"),
                industry=info.get("industry"),
                description=info.get("longBusinessSummary"),
                isin=info.get("isin"),
                currency_code=(info.get("currency") or "INR").upper(),
                facts=_company_facts(info),
                source=_source(symbol),
            )
        except YFTickerMissingError:
            return None
        except MarketDataError:
            raise
        except (ValidationError, AttributeError, KeyError, TypeError, ValueError) as exc:
            raise MarketDataError("Yahoo profile returned invalid data") from exc
        except Exception as exc:
            raise MarketDataError("Yahoo profile lookup failed") from exc

    def get_prices(
        self, security: SecurityKey, start_date: date, end_date: date
    ) -> PriceHistory:
        symbol = _yahoo_symbol(security)
        if start_date > end_date:
            raise ValueError("Start date must not be after end date")
        if end_date == date.max:
            raise ValueError("End date is too large")

        try:
            # yfinance treats end as exclusive; our contract treats it as inclusive.
            frame = yf.Ticker(symbol).history(
                start=start_date.isoformat(),
                end=(end_date + timedelta(days=1)).isoformat(),
                interval="1d",
                auto_adjust=True,
                actions=False,
                timeout=10,
                raise_errors=True,
            )
            source = _source(symbol)
            if frame.empty:
                return PriceHistory(
                    security=security,
                    adjustment="dividend_adjusted",
                    unavailable_reason="no_data",
                    source=source,
                )

            bars = []
            for trading_time, row in frame.iterrows():
                volume = row["Volume"]
                if volume is not None and not isnan(volume) and volume != int(volume):
                    raise ValueError("Trading volume must be a whole number")
                bars.append(
                    PriceBar(
                        trading_day=trading_time.date(),
                        open=Decimal(str(row["Open"])),
                        high=Decimal(str(row["High"])),
                        low=Decimal(str(row["Low"])),
                        close=Decimal(str(row["Close"])),
                        volume=None if volume is None or isnan(volume) else int(volume),
                    )
                )
            return PriceHistory(
                security=security,
                currency_code="INR",
                adjustment="dividend_adjusted",
                bars=bars,
                source=source,
            )
        except YFTickerMissingError:
            return PriceHistory(
                security=security,
                adjustment="dividend_adjusted",
                unavailable_reason="no_data",
                source=_source(symbol),
            )
        except (ValidationError, AttributeError, KeyError, TypeError, ValueError) as exc:
            raise MarketDataError("Yahoo price history returned invalid data") from exc
        except Exception as exc:
            raise MarketDataError("Yahoo price history request failed") from exc
