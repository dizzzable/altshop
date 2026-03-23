"""Add invite mode started timestamp.

Revision ID: 0048
Revises: 0047
Create Date: 2026-03-23 13:45:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0048"
down_revision: Union[str, None] = "0047"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "settings",
        sa.Column("invite_mode_started_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        """
        UPDATE settings
        SET invite_mode_started_at = TIMEZONE('utc', NOW())
        WHERE access_mode = 'INVITED'
          AND invite_mode_started_at IS NULL
        """
    )


def downgrade() -> None:
    op.drop_column("settings", "invite_mode_started_at")
