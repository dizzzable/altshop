"""Add renew_subscription_ids to transactions table

Revision ID: 0019
Revises: 0018
Create Date: 2024-12-05
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0019"
down_revision: Union[str, None] = "0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add renew_subscription_ids column to transactions table
    op.add_column(
        "transactions",
        sa.Column("renew_subscription_ids", postgresql.ARRAY(sa.Integer()), nullable=True),
    )


def downgrade() -> None:
    # Remove renew_subscription_ids column from transactions table
    op.drop_column("transactions", "renew_subscription_ids")