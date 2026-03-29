"""Add per-subscription renew items to transactions.

Revision ID: 0051
Revises: 0050
Create Date: 2026-03-29 16:10:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0051"
down_revision: Union[str, None] = "0050"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("transactions", sa.Column("renew_items", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("transactions", "renew_items")
