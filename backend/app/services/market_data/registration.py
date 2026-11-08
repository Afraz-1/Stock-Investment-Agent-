"""Register a verified Indian equity listing for later price ingestion."""

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Company, Exchange, Security

_EXCHANGES = {
    "NSE": "National Stock Exchange of India Limited",
    "BSE": "BSE Limited",
}
_SYMBOL = re.compile(r"[A-Z0-9][A-Z0-9&_.-]*")
_ISIN = re.compile(r"[A-Z0-9]{12}")


class CompanyNotFoundError(LookupError):
    """The supplied company ID does not exist."""


def register_listing(
    db: Session,
    *,
    exchange_code: str,
    symbol: str,
    legal_name: str | None = None,
    company_id: int | None = None,
    isin: str | None = None,
) -> Security:
    """Create or find one listing; the caller commits or rolls back.

    Supply a verified legal name to create a company, or a company ID to add
    another exchange listing for a company already in the registry.
    """

    exchange_code = exchange_code.strip().upper()
    symbol = symbol.strip().upper()
    legal_name = legal_name.strip() if legal_name is not None else None
    isin = isin.strip().upper() if isin is not None else None

    if exchange_code not in _EXCHANGES:
        raise ValueError("Exchange must be NSE or BSE")
    if not _SYMBOL.fullmatch(symbol) or len(symbol) > 32:
        raise ValueError("Invalid stock symbol")
    if legal_name is not None and (not legal_name or len(legal_name) > 255):
        raise ValueError("Legal name must contain 1 to 255 characters")
    if company_id is None and legal_name is None:
        raise ValueError("Provide a legal name or an existing company ID")
    if company_id is not None and company_id <= 0:
        raise ValueError("Company ID must be positive")
    if isin is not None and not _ISIN.fullmatch(isin):
        raise ValueError("ISIN must have 12 letters or digits")

    selected_company = None
    if company_id is not None:
        selected_company = db.get(Company, company_id)
        if selected_company is None:
            raise CompanyNotFoundError(f"Company {company_id} does not exist")
        if (
            legal_name is not None
            and selected_company.legal_name.casefold() != legal_name.casefold()
        ):
            raise ValueError("Legal name does not match the selected company")

    exchange = db.scalar(select(Exchange).where(Exchange.code == exchange_code))
    if exchange is None:
        exchange = Exchange(
            code=exchange_code,
            name=_EXCHANGES[exchange_code],
            country_code="IN",
            timezone_name="Asia/Kolkata",
        )
        db.add(exchange)
        db.flush()

    existing = db.scalar(
        select(Security).where(
            Security.exchange_id == exchange.id, Security.symbol == symbol
        )
    )
    if existing is not None:
        company = db.get(Company, existing.company_id)
        if company is None:
            raise CompanyNotFoundError(f"Company {existing.company_id} does not exist")
        if selected_company is not None and existing.company_id != selected_company.id:
            raise ValueError("Listing is already linked to a different company")
        if legal_name is not None and company.legal_name.casefold() != legal_name.casefold():
            raise ValueError("Listing is already linked to a different legal name")
        if isin is not None:
            if existing.isin is not None and existing.isin != isin:
                raise ValueError("Listing already has a different ISIN")
            existing.isin = isin
        db.flush()
        return existing

    if selected_company is None:
        company = Company(legal_name=legal_name, country_code="IN")
        db.add(company)
        db.flush()
    else:
        company = selected_company

    listing = Security(
        company_id=company.id,
        exchange_id=exchange.id,
        symbol=symbol,
        isin=isin,
        currency_code="INR",
    )
    db.add(listing)
    db.flush()
    return listing
