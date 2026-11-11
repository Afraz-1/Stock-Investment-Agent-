"""A dated research thesis and later outcome for one listing."""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Identity, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class InvestmentJournal(Base):
    __tablename__ = "investment_journal"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), Identity(), primary_key=True)
    security_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("securities.id", ondelete="RESTRICT"), nullable=False, index=True)
    thesis: Mapped[str] = mapped_column(String(4000), nullable=False)
    outcome: Mapped[str | None] = mapped_column(String(4000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
