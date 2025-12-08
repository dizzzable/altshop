"""Fix enum values: add ADDITIONAL to purchasetype, add DEVICES to promocode_reward_type

Revision ID: 0017
Revises: 0016
Create Date: 2024-12-05
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0017"
down_revision: Union[str, None] = "0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add ADDITIONAL to purchasetype enum
    op.execute("ALTER TYPE purchasetype ADD VALUE IF NOT EXISTS 'ADDITIONAL'")
    
    # Add DEVICES to promocode_reward_type enum
    op.execute("ALTER TYPE promocode_reward_type ADD VALUE IF NOT EXISTS 'DEVICES'")


def downgrade() -> None:
    # PostgreSQL doesn't support removing values from enums directly
    # To properly downgrade, you would need to:
    # 1. Create a new enum without the value
    # 2. Update all columns using the enum
    # 3. Drop the old enum
    # 4. Rename the new enum
    # This is complex and rarely needed, so we leave it as a no-op
    pass