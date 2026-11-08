"""A daily OHLCV observation for one exchange-listed security."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Identity,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DailyPrice(Base):
    """One provider's current observation for a listing and trading day."""

    __tablename__ = "daily_prices"
    __table_args__ = (
        UniqueConstraint(
            "security_id", "trading_day", "provider", "adjustment",
            name="uq_daily_prices_listing_day_source_adjustment",
        ),
        CheckConstraint(
            "open > 0 AND high > 0 AND low > 0 AND close > 0",
            name="ck_daily_prices_positive_ohlc",
        ),
        CheckConstraint(
            "low <= high AND low <= open AND open <= high "
            "AND low <= close AND close <= high",
            name="ck_daily_prices_ohlc_range",
        ),
        CheckConstraint(
            "volume IS NULL OR volume >= 0", name="ck_daily_prices_volume"
        ),
        CheckConstraint(
            "adjustment IN ('raw', 'split_adjusted', 'dividend_adjusted', 'unknown')",
            name="ck_daily_prices_adjustment",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    security_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("securities.id", ondelete="RESTRICT"), nullable=False
    )
    trading_day: Mapped[date] = mapped_column(Date, nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    adjustment: Mapped[str] = mapped_column(String(24), nullable=False)
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False)
    open: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    high: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    low: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    close: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    volume: Mapped[int | None] = mapped_column(BigInteger)
    source_retrieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    source_url: Mapped[str | None] = mapped_column(String(2048))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
