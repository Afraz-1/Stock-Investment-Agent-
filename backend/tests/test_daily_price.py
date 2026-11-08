"""Database checks for daily price identity and financial data integrity."""

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Base, Company, DailyPrice, Exchange, Security


@pytest.fixture
def session():
    engine = create_engine("sqlite+pysqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, record) -> None:
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(Company(id=1, legal_name="Example Limited", country_code="IN"))
        db.add(
            Exchange(
                id=1,
                code="NSE",
                name="National Stock Exchange",
                country_code="IN",
                timezone_name="Asia/Kolkata",
            )
        )
        db.flush()
        db.add(
            Security(
                id=1, company_id=1, exchange_id=1,
                symbol="EXAMPLE", currency_code="INR",
            )
        )
        db.commit()
        yield db
    engine.dispose()


def make_price(**changes) -> DailyPrice:
    fields = {
        "id": 1,
        "security_id": 1,
        "trading_day": date(2026, 11, 6),
        "provider": "yahoo_finance",
        "adjustment": "dividend_adjusted",
        "currency_code": "INR",
        "open": Decimal("100.25"),
        "high": Decimal("105.50"),
        "low": Decimal("99.75"),
        "close": Decimal("103.10"),
        "volume": 1000,
        "source_retrieved_at": datetime(2026, 11, 8, tzinfo=timezone.utc),
    }
    fields.update(changes)
    return DailyPrice(**fields)


def test_price_belongs_to_listing_and_keeps_source_identity(session: Session) -> None:
    session.add(make_price())
    session.commit()

    stored = session.get(DailyPrice, 1)
    assert stored is not None
    assert stored.security_id == 1
    assert stored.close == Decimal("103.10000000")
    assert stored.created_at is not None

    session.add(make_price(id=2))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()

    session.add(make_price(id=3, provider="other_provider"))
    session.commit()
    assert session.scalar(select(func.count()).select_from(DailyPrice)) == 2


@pytest.mark.parametrize(
    "changes",
    [
        {"open": Decimal("0")},
        {"high": Decimal("98")},
        {"volume": -1},
        {"adjustment": "made_up"},
        {"security_id": 999},
    ],
)
def test_invalid_or_unlinked_prices_are_rejected(session: Session, changes: dict) -> None:
    session.add(make_price(**changes))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()
    assert session.scalar(select(func.count()).select_from(DailyPrice)) == 0
