"""Add subscription_count to plans table

Revision ID: 0014
Revises: 0013
Create Date: 2024-12-03
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: Union[str, None] = "0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "plans",
        sa.Column(
            "subscription_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
        ),
    )
    # Remove server_default after adding the column
    op.alter_column("plans", "subscription_count", server_default=None)


def downgrade() -> None:
    op.drop_column("plans", "subscription_count")