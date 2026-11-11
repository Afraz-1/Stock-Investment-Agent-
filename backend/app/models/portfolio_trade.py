"""Manually recorded transactions for the local portfolio."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Identity, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PortfolioTrade(Base):
    __tablename__ = "portfolio_trades"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), Identity(), primary_key=True)
    security_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("securities.id", ondelete="RESTRICT"), nullable=False, index=True)
    trade_day: Mapped[date] = mapped_column(Date, nullable=False)
    side: Mapped[str] = mapped_column(String(4), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    fees: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    note: Mapped[str] = mapped_column(String(2000), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
