"""Create exchanges and securities tables.

Revision ID: 20261107_0002
Revises: 20261106_0001
"""

from alembic import op
import sqlalchemy as sa


revision = "20261107_0002"
down_revision = "20261106_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Store exchanges and their company-linked securities."""

    op.create_table(
        "exchanges",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("code", sa.String(length=16), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("country_code", sa.String(length=2), nullable=False),
        sa.Column("timezone_name", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_exchanges_code"),
    )
    op.create_table(
        "securities",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("company_id", sa.BigInteger(), nullable=False),
        sa.Column("exchange_id", sa.BigInteger(), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("isin", sa.String(length=12), nullable=True),
        sa.Column("currency_code", sa.String(length=3), nullable=False),
        sa.Column(
            "is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["exchange_id"], ["exchanges.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("exchange_id", "symbol", name="uq_securities_exchange_symbol"),
    )
    op.create_index("ix_securities_company_id", "securities", ["company_id"])


def downgrade() -> None:
    """Remove the securities and exchanges tables."""

    op.drop_index("ix_securities_company_id", table_name="securities")
    op.drop_table("securities")
    op.drop_table("exchanges")
