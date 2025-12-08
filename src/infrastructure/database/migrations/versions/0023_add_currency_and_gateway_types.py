"""Add new currency values (USDT, TON, BTC, ETH, LTC) and payment gateway types (CRYPTOPAY, ROBOKASSA, PAL24, WATA, PLATEGA)

Revision ID: 0023
Revises: 0022
Create Date: 2024-12-08
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0023"
down_revision: Union[str, None] = "0022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new currency values
    op.execute("ALTER TYPE currency ADD VALUE IF NOT EXISTS 'USDT'")
    op.execute("ALTER TYPE currency ADD VALUE IF NOT EXISTS 'TON'")
    op.execute("ALTER TYPE currency ADD VALUE IF NOT EXISTS 'BTC'")
    op.execute("ALTER TYPE currency ADD VALUE IF NOT EXISTS 'ETH'")
    op.execute("ALTER TYPE currency ADD VALUE IF NOT EXISTS 'LTC'")
    
    # Add new payment gateway types
    op.execute("ALTER TYPE payment_gateway_type ADD VALUE IF NOT EXISTS 'CRYPTOPAY'")
    op.execute("ALTER TYPE payment_gateway_type ADD VALUE IF NOT EXISTS 'ROBOKASSA'")
    op.execute("ALTER TYPE payment_gateway_type ADD VALUE IF NOT EXISTS 'PAL24'")
    op.execute("ALTER TYPE payment_gateway_type ADD VALUE IF NOT EXISTS 'WATA'")
    op.execute("ALTER TYPE payment_gateway_type ADD VALUE IF NOT EXISTS 'PLATEGA'")


def downgrade() -> None:
    # PostgreSQL doesn't support removing values from enums directly
    # To properly downgrade, you would need to:
    # 1. Create a new enum without the value
    # 2. Update all columns using the enum
    # 3. Drop the old enum
    # 4. Rename the new enum
    # This is complex and rarely needed, so we leave it as a no-op
    pass