"""Offline checks for registering one company's exchange listings."""

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.models import Base, Company, Exchange, Security
from app.services.market_data.registration import (
    CompanyNotFoundError,
    register_listing,
)


@pytest.fixture
def db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def test_registering_a_listing_creates_company_exchange_and_security(db: Session) -> None:
    listing = register_listing(
        db, exchange_code=" nse ", symbol=" tcs ",
        legal_name="Tata Consultancy Services Limited",
    )
    db.commit()

    assert listing.id is not None
    assert listing.symbol == "TCS"
    assert listing.currency_code == "INR"
    assert db.get(Company, listing.company_id).legal_name == "Tata Consultancy Services Limited"
    exchange = db.get(Exchange, listing.exchange_id)
    assert exchange.code == "NSE"
    assert exchange.timezone_name == "Asia/Kolkata"

    again = register_listing(
        db, exchange_code="NSE", symbol="TCS",
        legal_name="Tata Consultancy Services Limited",
    )
    db.commit()
    assert again.id == listing.id
    assert db.scalar(select(func.count()).select_from(Company)) == 1
    assert db.scalar(select(func.count()).select_from(Exchange)) == 1
    assert db.scalar(select(func.count()).select_from(Security)) == 1


def test_second_exchange_listing_reuses_explicit_company(db: Session) -> None:
    nse = register_listing(
        db, exchange_code="NSE", symbol="TCS",
        legal_name="Tata Consultancy Services Limited",
    )
    bse = register_listing(
        db, exchange_code="BSE", symbol="TCS", company_id=nse.company_id
    )
    db.commit()

    assert bse.company_id == nse.company_id
    assert bse.exchange_id != nse.exchange_id
    assert db.scalar(select(func.count()).select_from(Company)) == 1
    assert db.scalar(select(func.count()).select_from(Security)) == 2


def test_existing_listing_cannot_be_silently_reassigned(db: Session) -> None:
    original = register_listing(
        db, exchange_code="NSE", symbol="TCS",
        legal_name="Tata Consultancy Services Limited", isin="INE467B01029",
    )
    db.commit()
    with pytest.raises(ValueError, match="different legal name"):
        register_listing(
            db, exchange_code="NSE", symbol="TCS", legal_name="Different Company"
        )
    with pytest.raises(ValueError, match="different ISIN"):
        register_listing(
            db, exchange_code="NSE", symbol="TCS",
            company_id=original.company_id, isin="INE467B01028",
        )
    assert db.get(Security, original.id).isin == "INE467B01029"


@pytest.mark.parametrize(
    "options",
    [
        {"exchange_code": "NYSE", "symbol": "TCS", "legal_name": "Example"},
        {"exchange_code": "NSE", "symbol": "bad symbol", "legal_name": "Example"},
        {"exchange_code": "NSE", "symbol": "TCS", "legal_name": "   "},
        {"exchange_code": "NSE", "symbol": "TCS", "legal_name": "Example", "isin": "bad"},
    ],
)
def test_invalid_registration_inputs_are_rejected(db: Session, options: dict) -> None:
    with pytest.raises(ValueError):
        register_listing(db, **options)
    assert db.scalar(select(func.count()).select_from(Security)) == 0


def test_unknown_company_id_is_rejected(db: Session) -> None:
    with pytest.raises(CompanyNotFoundError):
        register_listing(db, exchange_code="BSE", symbol="TCS", company_id=999)
    assert db.scalar(select(func.count()).select_from(Exchange)) == 0
