"""Company identity, separate from any exchange-listed security."""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Identity, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Company(Base):
    """A legal company that may have multiple listed securities."""

    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), Identity(), primary_key=True
    )
    legal_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    country_code: Mapped[str] = mapped_column(String(2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
