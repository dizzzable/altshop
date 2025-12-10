"""Add multi subscription settings

Revision ID: 0027
Revises: 0026
Create Date: 2024-12-10 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0027"
down_revision: Union[str, None] = "0026"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add multi_subscription column to settings table (JSON column)
    op.add_column(
        "settings",
        sa.Column(
            "multi_subscription",
            sa.JSON(),
            nullable=False,
            server_default='{"enabled": true, "default_max_subscriptions": 5}',
        ),
    )
    
    # Add max_subscriptions column to users table
    # None = use global setting, -1 = unlimited, >0 = specific limit
    op.add_column(
        "users",
        sa.Column(
            "max_subscriptions",
            sa.Integer(),
            nullable=True,
            default=None,
        ),
    )


def downgrade() -> None:
    op.drop_column("settings", "multi_subscription")
    op.drop_column("users", "max_subscriptions")