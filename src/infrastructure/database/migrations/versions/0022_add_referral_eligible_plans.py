"""Add eligible_plan_ids to referral settings.

Revision ID: 0022
Revises: 0021
Create Date: 2024-12-07

"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "0022"
down_revision: Union[str, None] = "0021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add eligible_plan_ids field to referral JSON column in settings table."""
    # Cast json to jsonb for the operation, then back to json
    # Use jsonb operators which support the ? operator for key existence check
    op.execute(
        text(
            """
            UPDATE settings
            SET referral = (referral::jsonb || '{"eligible_plan_ids": []}'::jsonb)::json
            WHERE referral IS NOT NULL
            AND NOT (referral::jsonb ? 'eligible_plan_ids')
            """
        )
    )


def downgrade() -> None:
    """Remove eligible_plan_ids field from referral JSON column in settings table."""
    # Cast json to jsonb for the operation, then back to json
    op.execute(
        text(
            """
            UPDATE settings
            SET referral = (referral::jsonb - 'eligible_plan_ids')::json
            WHERE referral IS NOT NULL
            AND (referral::jsonb ? 'eligible_plan_ids')
            """
        )
    )