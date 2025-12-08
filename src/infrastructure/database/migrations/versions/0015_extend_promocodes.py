"""Extend promocodes table with availability and allowed_user_ids

Revision ID: 0015
Revises: 0014
Create Date: 2024-12-04
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY

revision: str = "0015"
down_revision: Union[str, None] = "0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enum type for promocode availability
    promocode_availability = sa.Enum(
        "ALL",
        "NEW",
        "EXISTING",
        "INVITED",
        "ALLOWED",
        name="promocode_availability",
    )
    promocode_availability.create(op.get_bind(), checkfirst=True)

    # Add availability column
    op.add_column(
        "promocodes",
        sa.Column(
            "availability",
            promocode_availability,
            nullable=False,
            server_default="ALL",
        ),
    )
    # Remove server_default after adding the column
    op.alter_column("promocodes", "availability", server_default=None)

    # Add allowed_user_ids column
    op.add_column(
        "promocodes",
        sa.Column(
            "allowed_user_ids",
            ARRAY(sa.BigInteger()),
            nullable=True,
            server_default="{}",
        ),
    )
    # Remove server_default after adding the column
    op.alter_column("promocodes", "allowed_user_ids", server_default=None)


def downgrade() -> None:
    op.drop_column("promocodes", "allowed_user_ids")
    op.drop_column("promocodes", "availability")
    
    # Drop enum type
    sa.Enum(name="promocode_availability").drop(op.get_bind(), checkfirst=True)