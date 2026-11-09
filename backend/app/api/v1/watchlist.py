"""Local watchlist and deliberate price refresh actions."""

from datetime import date, timezone
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response
from pydantic import AwareDatetime, BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.v1.stocks import get_market_data_provider
from app.db.session import get_db
from app.models import Company, DailyPrice, Exchange, Security, WatchlistItem
from app.services.market_data.ingestion import ingest_daily_prices
from app.services.market_data.provider import MarketDataProvider
from app.services.market_data.registration import register_listing
from app.services.market_data.schemas import SecurityKey

router = APIRouter(prefix="/api/v1/watchlist", tags=["watchlist"])
ExchangeCode = Literal["NSE", "BSE"]
StockSymbol = Annotated[
    str, Path(min_length=1, max_length=32, pattern=r"^[A-Za-z0-9][A-Za-z0-9&_.-]*$")
]


class WatchlistCreate(BaseModel):
    """The user confirms a listing's legal name before saving it locally."""

    exchange_code: ExchangeCode
    symbol: str = Field(
        min_length=1, max_length=32, pattern=r"^[A-Za-z0-9][A-Za-z0-9&_.-]*$"
    )
    legal_name: str = Field(min_length=1, max_length=255)
    isin: str | None = Field(default=None, pattern=r"^[A-Z0-9]{12}$")


class WatchlistEntry(BaseModel):
    id: int
    security: SecurityKey
    legal_name: str
    isin: str | None
    saved_price_count: int
    latest_saved_day: date | None
    added_at: AwareDatetime


class RefreshResult(BaseModel):
    security: SecurityKey
    start: date
    end: date
    bars_received: int


def _entries(db: Session) -> list[WatchlistEntry]:
    """Load watchlist identity and saved-price counts in two queries."""

    listings = db.execute(
        select(WatchlistItem, Security, Exchange, Company)
        .join(Security, WatchlistItem.security_id == Security.id)
        .join(Exchange, Security.exchange_id == Exchange.id)
        .join(Company, Security.company_id == Company.id)
        .order_by(WatchlistItem.added_at, WatchlistItem.id)
    ).all()
    ids = [security.id for _, security, _, _ in listings]
    stats: dict[int, tuple[int, date | None]] = {}
    if ids:
        stats = {
            security_id: (count, latest)
            for security_id, count, latest in db.execute(
                select(
                    DailyPrice.security_id,
                    func.count(DailyPrice.id),
                    func.max(DailyPrice.trading_day),
                )
                .where(
                    DailyPrice.security_id.in_(ids),
                    DailyPrice.provider == "yahoo_finance",
                    DailyPrice.adjustment == "dividend_adjusted",
                )
                .group_by(DailyPrice.security_id)
            )
        }
    return [
        WatchlistEntry(
            id=item.id,
            security=SecurityKey(
                exchange_code=exchange.code, symbol=security.symbol
            ),
            legal_name=company.legal_name,
            isin=security.isin,
            saved_price_count=stats.get(security.id, (0, None))[0],
            latest_saved_day=stats.get(security.id, (0, None))[1],
            added_at=item.added_at
            if item.added_at.tzinfo
            else item.added_at.replace(tzinfo=timezone.utc),
        )
        for item, security, exchange, company in listings
    ]


def _tracked_security(db: Session, exchange: str, symbol: str) -> Security | None:
    return db.scalar(
        select(Security)
        .join(Exchange, Security.exchange_id == Exchange.id)
        .join(WatchlistItem, WatchlistItem.security_id == Security.id)
        .where(Exchange.code == exchange, Security.symbol == symbol.upper())
    )


@router.get("", response_model=list[WatchlistEntry])
def list_watchlist(db: Annotated[Session, Depends(get_db)]) -> list[WatchlistEntry]:
    """List locally tracked listings and their saved-price coverage."""

    try:
        return _entries(db)
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Database unavailable") from exc


@router.post("", response_model=WatchlistEntry, status_code=201)
def add_to_watchlist(
    body: WatchlistCreate,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    provider: Annotated[MarketDataProvider, Depends(get_market_data_provider)],
) -> WatchlistEntry:
    """Verify an exact provider listing, register it, and track it locally."""

    key = SecurityKey(exchange_code=body.exchange_code, symbol=body.symbol.upper())
    profile = provider.get_profile(key)
    if profile is None or profile.security != key:
        raise HTTPException(status_code=404, detail="Stock listing not found")
    if profile.currency_code not in (None, "INR"):
        raise HTTPException(status_code=422, detail="Expected an INR listing")

    try:
        matching_company_id = None
        if body.isin:
            matching_company_id = db.scalar(
                select(Security.company_id).where(Security.isin == body.isin).limit(1)
            )
        security = register_listing(
            db,
            exchange_code=key.exchange_code,
            symbol=key.symbol,
            legal_name=body.legal_name,
            company_id=matching_company_id,
            isin=body.isin,
        )
        existing = db.scalar(
            select(WatchlistItem).where(WatchlistItem.security_id == security.id)
        )
        if existing is None:
            db.add(WatchlistItem(security_id=security.id))
        else:
            response.status_code = 200
        db.commit()
        return next(entry for entry in _entries(db) if entry.security == key)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="Listing changed; retry the request"
        ) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="Database unavailable") from exc


@router.delete("/{exchange}/{symbol}", status_code=204)
def remove_from_watchlist(
    exchange: ExchangeCode,
    symbol: StockSymbol,
    db: Annotated[Session, Depends(get_db)],
) -> None:
    """Untrack a listing while retaining its company and saved prices."""

    try:
        security = _tracked_security(db, exchange, symbol)
        if security is None:
            raise HTTPException(status_code=404, detail="Listing is not tracked")
        item = db.scalar(
            select(WatchlistItem).where(WatchlistItem.security_id == security.id)
        )
        db.delete(item)
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="Database unavailable") from exc


@router.post("/{exchange}/{symbol}/refresh-prices", response_model=RefreshResult)
def refresh_watchlist_prices(
    exchange: ExchangeCode,
    symbol: StockSymbol,
    start: Annotated[date, Query(description="First trading date, inclusive")],
    end: Annotated[date, Query(description="Last trading date, inclusive")],
    db: Annotated[Session, Depends(get_db)],
    provider: Annotated[MarketDataProvider, Depends(get_market_data_provider)],
) -> RefreshResult:
    """Fetch up to one year of bars for a tracked listing and commit them."""

    if start > end or end == date.max or (end - start).days > 366:
        raise HTTPException(status_code=422, detail="Choose a range of at most 366 days")
    try:
        security = _tracked_security(db, exchange, symbol)
        if security is None:
            raise HTTPException(status_code=404, detail="Listing is not tracked")
        count = ingest_daily_prices(db, provider, security.id, start, end)
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="Database unavailable") from exc
    return RefreshResult(
        security=SecurityKey(exchange_code=exchange, symbol=security.symbol),
        start=start,
        end=end,
        bars_received=count,
    )
