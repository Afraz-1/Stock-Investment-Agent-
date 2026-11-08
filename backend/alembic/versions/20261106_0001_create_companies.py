"""Create companies table.

Revision ID: 20261106_0001
Revises:
"""

from alembic import op
import sqlalchemy as sa


revision = "20261106_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the first EquityIQ data table."""

    op.create_table(
        "companies",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("legal_name", sa.String(length=255), nullable=False),
        sa.Column("country_code", sa.String(length=2), nullable=False),
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
    )
    op.create_index("ix_companies_legal_name", "companies", ["legal_name"])


def downgrade() -> None:
    """Remove the companies table."""

    op.drop_index("ix_companies_legal_name", table_name="companies")
    op.drop_table("companies")
