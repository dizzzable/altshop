"""Add OTHER value to device_type enum and backfill imported subscriptions.

Revision ID: 0032
Revises: 0031
Create Date: 2026-02-26 12:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0032"
down_revision: Union[str, None] = "0031"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE device_type ADD VALUE IF NOT EXISTS 'OTHER'")

    op.execute(
        sa.text(
            """
            UPDATE subscriptions
            SET device_type = 'OTHER'
            WHERE device_type IS NULL
              AND (
                UPPER(COALESCE(plan->>'tag', '')) = 'IMPORTED'
                OR UPPER(COALESCE(plan->>'name', '')) = 'IMPORTED'
                OR COALESCE(NULLIF(plan->>'id', ''), '-1')::int <= 0
              )
            """
        )
    )


def downgrade() -> None:
    # PostgreSQL does not support removing enum values directly.
    pass
