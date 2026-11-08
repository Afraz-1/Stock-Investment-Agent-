"""Offline tests for exchange-specific security symbols."""

from pytest import raises
from sqlalchemy import create_engine, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Base, Company, Exchange, Security


def test_symbol_is_unique_within_each_exchange() -> None:
    test_engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(test_engine)

    try:
        with Session(test_engine) as session:
            session.add(Company(id=1, legal_name="Example Limited", country_code="IN"))
            session.add_all(
                [
                    Exchange(
                        id=1,
                        code="NSE",
                        name="National Stock Exchange",
                        country_code="IN",
                        timezone_name="Asia/Kolkata",
                    ),
                    Exchange(
                        id=2,
                        code="BSE",
                        name="BSE Limited",
                        country_code="IN",
                        timezone_name="Asia/Kolkata",
                    ),
                ]
            )
            session.commit()

            session.add_all(
                [
                    Security(
                        id=1,
                        company_id=1,
                        exchange_id=1,
                        symbol="EXAMPLE",
                        currency_code="INR",
                    ),
                    Security(
                        id=2,
                        company_id=1,
                        exchange_id=2,
                        symbol="EXAMPLE",
                        currency_code="INR",
                    ),
                ]
            )
            session.commit()

            session.add(
                Security(
                    id=3,
                    company_id=1,
                    exchange_id=1,
                    symbol="EXAMPLE",
                    currency_code="INR",
                )
            )
            with raises(IntegrityError):
                session.commit()
            session.rollback()

            assert session.scalar(select(func.count()).select_from(Security)) == 2
    finally:
        test_engine.dispose()
