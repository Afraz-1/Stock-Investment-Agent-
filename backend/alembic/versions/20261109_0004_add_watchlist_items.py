"""Track registered listings without deleting their price history.

Revision ID: 20261109_0004
Revises: 20261108_0003
"""

from alembic import op
import sqlalchemy as sa


revision = "20261109_0004"
down_revision = "20261108_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "watchlist_items",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("security_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "added_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["security_id"], ["securities.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("security_id", name="uq_watchlist_items_security_id"),
    )
    # Preserve listings registered before this feature was added, including NSE:TCS.
    op.execute("INSERT INTO watchlist_items (security_id) SELECT id FROM securities")


def downgrade() -> None:
    op.drop_table("watchlist_items")
