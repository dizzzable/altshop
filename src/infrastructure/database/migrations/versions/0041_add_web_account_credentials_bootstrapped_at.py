"""Add credentials bootstrap marker to web_accounts.

Revision ID: 0041
Revises: 0040
Create Date: 2026-03-07 15:10:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0041"
down_revision: Union[str, None] = "0040"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "web_accounts",
        sa.Column(
            "credentials_bootstrapped_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.execute(
        sa.text(
            """
            UPDATE web_accounts
            SET credentials_bootstrapped_at = COALESCE(created_at, timezone('UTC', now()))
            WHERE credentials_bootstrapped_at IS NULL
            """
        )
    )


def downgrade() -> None:
    op.drop_column("web_accounts", "credentials_bootstrapped_at")
