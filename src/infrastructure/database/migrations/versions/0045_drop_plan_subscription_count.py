"""Drop deprecated plan subscription_count field.

Revision ID: 0045
Revises: 0044
Create Date: 2026-03-08 01:20:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0045"
down_revision: Union[str, None] = "0044"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("plans", "subscription_count")


def downgrade() -> None:
    op.add_column(
        "plans",
        sa.Column("subscription_count", sa.Integer(), nullable=False, server_default="1"),
    )
    op.alter_column("plans", "subscription_count", server_default=None)
