"""Add T-Bank gateway, market currencies, and partner balance fields.

Revision ID: 0044
Revises: 0043
Create Date: 2026-03-08 00:25:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0044"
down_revision: Union[str, None] = "0043"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE payment_gateway_type ADD VALUE IF NOT EXISTS 'TBANK'")

    for currency in ("BNB", "DASH", "SOL", "XMR", "USDC", "TRX"):
        op.execute(f"ALTER TYPE currency ADD VALUE IF NOT EXISTS '{currency}'")

    op.execute("ALTER TYPE crypto_asset ADD VALUE IF NOT EXISTS 'TRX'")

    op.add_column(
        "users",
        sa.Column(
            "partner_balance_currency_override",
            postgresql.ENUM(name="currency", create_type=False),
            nullable=True,
        ),
    )

    op.add_column(
        "partner_withdrawals",
        sa.Column("requested_amount", sa.Numeric(24, 8), nullable=True),
    )
    op.add_column(
        "partner_withdrawals",
        sa.Column(
            "requested_currency",
            postgresql.ENUM(name="currency", create_type=False),
            nullable=True,
        ),
    )
    op.add_column(
        "partner_withdrawals",
        sa.Column("quote_rate", sa.Numeric(24, 8), nullable=True),
    )
    op.add_column(
        "partner_withdrawals",
        sa.Column("quote_source", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("partner_withdrawals", "quote_source")
    op.drop_column("partner_withdrawals", "quote_rate")
    op.drop_column("partner_withdrawals", "requested_currency")
    op.drop_column("partner_withdrawals", "requested_amount")
    op.drop_column("users", "partner_balance_currency_override")
