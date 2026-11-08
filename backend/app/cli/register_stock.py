"""Register a stock listing from the local terminal."""

import argparse

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.connection import create_database_engine
from app.services.market_data.registration import (
    CompanyNotFoundError,
    register_listing,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Register an NSE or BSE stock listing")
    parser.add_argument("--exchange", choices=("NSE", "BSE"), required=True)
    parser.add_argument("--symbol", required=True)
    company = parser.add_mutually_exclusive_group(required=True)
    company.add_argument("--legal-name", help="Verified legal name for a new company")
    company.add_argument("--company-id", type=int, help="Link to an existing company")
    parser.add_argument("--isin", help="Optional 12-character security identifier")
    args = parser.parse_args()

    settings = Settings()
    engine = create_database_engine(
        settings.database_url.get_secret_value() if settings.database_url else None
    )
    if engine is None:
        parser.error("EQUITYIQ_DATABASE_URL is required")

    try:
        with Session(engine) as db:
            try:
                listing = register_listing(
                    db,
                    exchange_code=args.exchange,
                    symbol=args.symbol,
                    legal_name=args.legal_name,
                    company_id=args.company_id,
                    isin=args.isin,
                )
                db.commit()
                print(f"Company ID: {listing.company_id}; security ID: {listing.id}")
            except (ValueError, CompanyNotFoundError) as exc:
                db.rollback()
                parser.error(str(exc))
            except IntegrityError:
                db.rollback()
                parser.error("Registration conflicted with an existing database row")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
