"""Create daily price history storage.

Revision ID: 20261108_0003
Revises: 20261107_0002
"""

from alembic import op
import sqlalchemy as sa


revision = "20261108_0003"
down_revision = "20261107_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Store daily prices with source and adjustment identity."""

    op.create_table(
        "daily_prices",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("security_id", sa.BigInteger(), nullable=False),
        sa.Column("trading_day", sa.Date(), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("adjustment", sa.String(length=24), nullable=False),
        sa.Column("currency_code", sa.String(length=3), nullable=False),
        sa.Column("open", sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column("high", sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column("low", sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column("close", sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column("volume", sa.BigInteger(), nullable=True),
        sa.Column("source_retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_url", sa.String(length=2048), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.CheckConstraint(
            "open > 0 AND high > 0 AND low > 0 AND close > 0",
            name="ck_daily_prices_positive_ohlc",
        ),
        sa.CheckConstraint(
            "low <= high AND low <= open AND open <= high "
            "AND low <= close AND close <= high",
            name="ck_daily_prices_ohlc_range",
        ),
        sa.CheckConstraint(
            "volume IS NULL OR volume >= 0", name="ck_daily_prices_volume"
        ),
        sa.CheckConstraint(
            "adjustment IN ('raw', 'split_adjusted', 'dividend_adjusted', 'unknown')",
            name="ck_daily_prices_adjustment",
        ),
        sa.ForeignKeyConstraint(["security_id"], ["securities.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "security_id", "trading_day", "provider", "adjustment",
            name="uq_daily_prices_listing_day_source_adjustment",
        ),
    )


def downgrade() -> None:
    """Remove the daily price table."""

    op.drop_table("daily_prices")
