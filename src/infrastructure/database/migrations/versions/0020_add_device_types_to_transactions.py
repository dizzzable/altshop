"""Add device_types to transactions

Revision ID: 0020
Revises: 0019
Create Date: 2025-12-07

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0020"
down_revision: Union[str, None] = "0019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add device_types column to transactions table
    op.add_column(
        "transactions",
        sa.Column("device_types", sa.ARRAY(sa.String()), nullable=True),
    )


def downgrade() -> None:
    # Remove device_types column from transactions table
    op.drop_column("transactions", "device_types")