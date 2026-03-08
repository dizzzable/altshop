"""Add allowed_plan_ids to promocodes.

Revision ID: 0035
Revises: 0034
Create Date: 2026-03-01 13:40:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY

# revision identifiers, used by Alembic.
revision: str = "0035"
down_revision: Union[str, None] = "0034"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "promocodes",
        sa.Column(
            "allowed_plan_ids",
            ARRAY(sa.BigInteger()),
            nullable=True,
            server_default=sa.text("'{}'::bigint[]"),
        ),
    )
    op.alter_column("promocodes", "allowed_plan_ids", server_default=None)


def downgrade() -> None:
    op.drop_column("promocodes", "allowed_plan_ids")
