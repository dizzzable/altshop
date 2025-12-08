"""Add device_type to subscriptions table

Revision ID: 0016
Revises: 0015
Create Date: 2024-12-05
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0016"
down_revision: Union[str, None] = "0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create the device_type enum
    device_type_enum = sa.Enum(
        "ANDROID", "IPHONE", "WINDOWS", "MAC",
        name="device_type",
        create_type=True,
    )
    device_type_enum.create(op.get_bind(), checkfirst=True)
    
    # Add the device_type column
    op.add_column(
        "subscriptions",
        sa.Column(
            "device_type",
            device_type_enum,
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("subscriptions", "device_type")
    
    # Drop the enum type
    sa.Enum(name="device_type").drop(op.get_bind(), checkfirst=True)