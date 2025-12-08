"""Add renew_subscription_id to transactions table

Revision ID: 0018
Revises: 0017
Create Date: 2024-12-05
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0018"
down_revision: Union[str, None] = "0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add renew_subscription_id column to transactions table
    op.add_column(
        "transactions",
        sa.Column("renew_subscription_id", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    # Remove renew_subscription_id column from transactions table
    op.drop_column("transactions", "renew_subscription_id")