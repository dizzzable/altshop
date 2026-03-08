"""Add crypto payment assets and transaction payment_asset column

Revision ID: 0043
Revises: 0042
Create Date: 2026-03-07 22:20:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0043"
down_revision: Union[str, None] = "0042"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    crypto_asset_enum = postgresql.ENUM(
        "USDT",
        "TON",
        "BTC",
        "ETH",
        "LTC",
        "BNB",
        "DASH",
        "SOL",
        "XMR",
        "USDC",
        name="crypto_asset",
    )
    crypto_asset_enum.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "transactions",
        sa.Column(
            "payment_asset",
            postgresql.ENUM(name="crypto_asset", create_type=False),
            nullable=True,
        ),
    )
    op.execute(
        "UPDATE payment_gateways SET currency = 'USD' "
        "WHERE type = 'CRYPTOPAY' AND currency = 'USDT'"
    )


def downgrade() -> None:
    op.drop_column("transactions", "payment_asset")
    postgresql.ENUM(name="crypto_asset").drop(op.get_bind(), checkfirst=True)
