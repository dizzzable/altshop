"""Add additional payment gateway types

Revision ID: 0042
Revises: 0041
Create Date: 2026-03-07 17:20:00.000000
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "0042"
down_revision = "0041"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE payment_gateway_type ADD VALUE IF NOT EXISTS 'STRIPE'")
    op.execute("ALTER TYPE payment_gateway_type ADD VALUE IF NOT EXISTS 'MULENPAY'")
    op.execute("ALTER TYPE payment_gateway_type ADD VALUE IF NOT EXISTS 'CLOUDPAYMENTS'")


def downgrade() -> None:
    # PostgreSQL enums do not support dropping values safely in-place.
    pass
