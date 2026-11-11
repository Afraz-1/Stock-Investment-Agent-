"""Add manual portfolio trades and investment journal.

Revision ID: 20261111_0005
Revises: 20261109_0004
"""

from alembic import op
import sqlalchemy as sa

revision = "20261111_0005"
down_revision = "20261109_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "portfolio_trades",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("security_id", sa.BigInteger(), sa.ForeignKey("securities.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("trade_day", sa.Date(), nullable=False),
        sa.Column("side", sa.String(4), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 6), nullable=False),
        sa.Column("price", sa.Numeric(20, 4), nullable=False),
        sa.Column("fees", sa.Numeric(20, 4), nullable=False),
        sa.Column("note", sa.String(2000), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("side IN ('buy', 'sell')", name="ck_portfolio_trades_side"),
        sa.CheckConstraint("quantity > 0", name="ck_portfolio_trades_quantity"),
        sa.CheckConstraint("price > 0", name="ck_portfolio_trades_price"),
        sa.CheckConstraint("fees >= 0", name="ck_portfolio_trades_fees"),
    )
    op.create_index("ix_portfolio_trades_security_id", "portfolio_trades", ["security_id"])
    op.create_table(
        "investment_journal",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("security_id", sa.BigInteger(), sa.ForeignKey("securities.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("thesis", sa.String(4000), nullable=False),
        sa.Column("outcome", sa.String(4000)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_investment_journal_security_id", "investment_journal", ["security_id"])


def downgrade() -> None:
    op.drop_table("investment_journal")
    op.drop_table("portfolio_trades")
