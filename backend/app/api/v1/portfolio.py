"""Local, manually entered holdings and investment journal."""

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import AwareDatetime, BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Exchange, InvestmentJournal, PortfolioTrade, Security, WatchlistItem
from app.services.market_data.schemas import SecurityKey

router = APIRouter(prefix="/api/v1/portfolio", tags=["portfolio"])


class TradeCreate(BaseModel):
    security: SecurityKey
    trade_day: date
    side: Literal["buy", "sell"]
    quantity: Decimal = Field(gt=0, max_digits=18, decimal_places=6)
    price: Decimal = Field(gt=0, max_digits=20, decimal_places=4)
    fees: Decimal = Field(default=Decimal("0"), ge=0, max_digits=20, decimal_places=4)
    note: str = Field(default="", max_length=2000)


class TradeRead(TradeCreate):
    id: int
    created_at: AwareDatetime


class Holding(BaseModel):
    security: SecurityKey
    quantity: Decimal
    average_cost: Decimal
    cost_basis: Decimal
    realized_pnl: Decimal


class JournalCreate(BaseModel):
    security: SecurityKey
    thesis: str = Field(min_length=1, max_length=4000)


class JournalOutcome(BaseModel):
    outcome: str = Field(min_length=1, max_length=4000)


class JournalRead(JournalCreate):
    id: int
    outcome: str | None
    created_at: AwareDatetime
    updated_at: AwareDatetime


class PortfolioRead(BaseModel):
    holdings: list[Holding]
    trades: list[TradeRead]
    journal: list[JournalRead]
    realized_pnl: Decimal


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _security(db: Session, key: SecurityKey, *, lock: bool = False) -> Security:
    query = (
        select(Security)
        .join(Exchange, Security.exchange_id == Exchange.id)
        .join(WatchlistItem, WatchlistItem.security_id == Security.id)
        .where(Exchange.code == key.exchange_code, Security.symbol == key.symbol)
    )
    security = db.scalar(query.with_for_update() if lock else query)
    if security is None:
        raise HTTPException(404, "Add this listing to My stocks first")
    if security.currency_code != "INR":
        raise HTTPException(422, "Portfolio currently supports INR listings only")
    return security


def _identities(db: Session) -> dict[int, SecurityKey]:
    rows = db.execute(
        select(Security, Exchange).join(Exchange, Security.exchange_id == Exchange.id)
    )
    return {
        security.id: SecurityKey(exchange_code=exchange.code, symbol=security.symbol)
        for security, exchange in rows
    }


def _trade(row: PortfolioTrade, key: SecurityKey) -> TradeRead:
    return TradeRead(
        id=row.id,
        security=key,
        trade_day=row.trade_day,
        side=row.side,
        quantity=row.quantity,
        price=row.price,
        fees=row.fees,
        note=row.note,
        created_at=_aware(row.created_at),
    )


def _journal(row: InvestmentJournal, key: SecurityKey) -> JournalRead:
    return JournalRead(
        id=row.id,
        security=key,
        thesis=row.thesis,
        outcome=row.outcome,
        created_at=_aware(row.created_at),
        updated_at=_aware(row.updated_at),
    )


def _holdings(trades: list[PortfolioTrade], identities: dict[int, SecurityKey]) -> tuple[list[Holding], Decimal]:
    state: dict[int, tuple[Decimal, Decimal, Decimal]] = {}
    for row in trades:
        quantity, cost, realized = state.get(
            row.security_id, (Decimal(0), Decimal(0), Decimal(0))
        )
        if row.side == "buy":
            quantity += row.quantity
            cost += row.quantity * row.price + row.fees
        else:
            if row.quantity > quantity:
                raise ValueError("A sell exceeds the available holding at its trade date")
            allocated_cost = (
                cost if row.quantity == quantity else cost * row.quantity / quantity
            )
            realized += row.quantity * row.price - row.fees - allocated_cost
            quantity -= row.quantity
            cost -= allocated_cost
        state[row.security_id] = (quantity, cost, realized)
    holdings = [
        Holding(
            security=identities[security_id],
            quantity=quantity,
            average_cost=cost / quantity,
            cost_basis=cost,
            realized_pnl=realized,
        )
        for security_id, (quantity, cost, realized) in state.items()
        if quantity > 0
    ]
    return holdings, sum((item[2] for item in state.values()), Decimal(0))


@router.get("", response_model=PortfolioRead)
def read_portfolio(db: Annotated[Session, Depends(get_db)]) -> PortfolioRead:
    try:
        identities = _identities(db)
        trades = db.scalars(
            select(PortfolioTrade).order_by(PortfolioTrade.trade_day, PortfolioTrade.id)
        ).all()
        journal = db.scalars(
            select(InvestmentJournal).order_by(
                InvestmentJournal.created_at.desc(), InvestmentJournal.id.desc()
            )
        ).all()
        holdings, realized = _holdings(trades, identities)
        return PortfolioRead(
            holdings=holdings,
            trades=[_trade(row, identities[row.security_id]) for row in reversed(trades)],
            journal=[_journal(row, identities[row.security_id]) for row in journal],
            realized_pnl=realized,
        )
    except SQLAlchemyError as exc:
        raise HTTPException(503, "Database unavailable") from exc


@router.post("/trades", response_model=TradeRead, status_code=201)
def add_trade(body: TradeCreate, db: Annotated[Session, Depends(get_db)]) -> TradeRead:
    if body.trade_day > datetime.now(ZoneInfo("Asia/Kolkata")).date():
        raise HTTPException(422, "Trade day cannot be in the future")
    try:
        security = _security(db, body.security, lock=True)
        row = PortfolioTrade(
            security_id=security.id,
            trade_day=body.trade_day,
            side=body.side,
            quantity=body.quantity,
            price=body.price,
            fees=body.fees,
            note=body.note.strip(),
        )
        db.add(row)
        db.flush()
        trades = db.scalars(
            select(PortfolioTrade).order_by(PortfolioTrade.trade_day, PortfolioTrade.id)
        ).all()
        try:
            _holdings(trades, _identities(db))
        except ValueError as exc:
            db.rollback()
            raise HTTPException(422, str(exc)) from exc
        db.commit()
        db.refresh(row)
        return _trade(row, body.security)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(503, "Database unavailable") from exc


@router.delete("/trades/{trade_id}", status_code=204)
def remove_trade(trade_id: int, db: Annotated[Session, Depends(get_db)]) -> Response:
    """Correct an entry only when the remaining chronological ledger stays valid."""
    try:
        row = db.get(PortfolioTrade, trade_id)
        if row is None:
            raise HTTPException(404, "Trade not found")
        db.scalar(select(Security).where(Security.id == row.security_id).with_for_update())
        db.delete(row)
        db.flush()
        remaining = db.scalars(
            select(PortfolioTrade).order_by(PortfolioTrade.trade_day, PortfolioTrade.id)
        ).all()
        try:
            _holdings(remaining, _identities(db))
        except ValueError as exc:
            db.rollback()
            raise HTTPException(
                422, "Removing this trade would leave a sell without enough shares"
            ) from exc
        db.commit()
        return Response(status_code=204)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(503, "Database unavailable") from exc


@router.post("/journal", response_model=JournalRead, status_code=201)
def add_journal(body: JournalCreate, db: Annotated[Session, Depends(get_db)]) -> JournalRead:
    try:
        security = _security(db, body.security)
        row = InvestmentJournal(security_id=security.id, thesis=body.thesis.strip())
        if not row.thesis:
            raise HTTPException(422, "Thesis cannot be blank")
        db.add(row)
        db.commit()
        db.refresh(row)
        return _journal(row, body.security)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(503, "Database unavailable") from exc


@router.patch("/journal/{entry_id}", response_model=JournalRead)
def update_outcome(entry_id: int, body: JournalOutcome, db: Annotated[Session, Depends(get_db)]) -> JournalRead:
    if not body.outcome.strip():
        raise HTTPException(422, "Outcome cannot be blank")
    try:
        row = db.get(InvestmentJournal, entry_id)
        if row is None:
            raise HTTPException(404, "Journal entry not found")
        identities = _identities(db)
        row.outcome = body.outcome.strip()
        db.commit()
        db.refresh(row)
        return _journal(row, identities[row.security_id])
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(503, "Database unavailable") from exc
