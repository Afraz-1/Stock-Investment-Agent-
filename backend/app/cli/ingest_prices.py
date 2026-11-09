"""Fetch and save daily prices for a locally registered stock listing."""

import argparse
import re
from datetime import date

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.connection import create_database_engine
from app.models import Exchange, Security
from app.services.market_data.ingestion import (
    SecurityNotFoundError,
    ingest_daily_prices,
)
from app.services.market_data.provider import MarketDataError
from app.services.market_data.yahoo import YahooMarketDataProvider


def _parse_date(value: str) -> date:
    """Give argparse a readable error for an invalid ISO date."""

    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) is None:
        raise argparse.ArgumentTypeError("Use a date in YYYY-MM-DD format")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Use a date in YYYY-MM-DD format") from exc


def main(argv: list[str] | None = None) -> None:
    """Resolve an exchange listing, fetch its bars, and commit them locally."""

    parser = argparse.ArgumentParser(description="Save daily stock prices to PostgreSQL")
    parser.add_argument("--exchange", choices=("NSE", "BSE"), required=True)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--start", type=_parse_date, required=True)
    parser.add_argument("--end", type=_parse_date, required=True)
    args = parser.parse_args(argv)
    if args.start > args.end or args.end == date.max:
        parser.error("Invalid price date range")

    settings = Settings()
    engine = create_database_engine(
        settings.database_url.get_secret_value() if settings.database_url else None
    )
    if engine is None:
        parser.error("EQUITYIQ_DATABASE_URL is required")

    try:
        with Session(engine) as db:
            try:
                security_id = db.scalar(
                    select(Security.id)
                    .join(Exchange, Security.exchange_id == Exchange.id)
                    .where(
                        Exchange.code == args.exchange,
                        Security.symbol == args.symbol.strip().upper(),
                    )
                )
                if security_id is None:
                    parser.error("Listing is not registered; run register_stock first")

                count = ingest_daily_prices(
                    db, YahooMarketDataProvider(), security_id, args.start, args.end
                )
                db.commit()
                print(
                    f"Received {count} daily bars for {args.exchange}:"
                    f"{args.symbol.strip().upper()} (security ID {security_id})"
                )
            except (ValueError, SecurityNotFoundError) as exc:
                db.rollback()
                parser.error(str(exc))
            except MarketDataError:
                db.rollback()
                parser.error("Market data provider request failed")
            except SQLAlchemyError:
                db.rollback()
                parser.error("Database operation failed")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
