"""Repair purchasetype enum to use UPGRADE instead of legacy CHANGE.

Revision ID: 0052
Revises: 0051
Create Date: 2026-04-10 19:30:00.000000
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0052"
down_revision: Union[str, None] = "0051"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE purchasetype RENAME TO purchasetype_old")
    op.execute(
        "CREATE TYPE purchasetype AS ENUM ('NEW', 'RENEW', 'UPGRADE', 'ADDITIONAL')"
    )
    op.execute("""
        ALTER TABLE transactions
        ALTER COLUMN purchase_type TYPE purchasetype
        USING (
            CASE
                WHEN purchase_type::text = 'CHANGE' THEN 'UPGRADE'
                ELSE purchase_type::text
            END
        )::purchasetype
    """)
    op.execute("DROP TYPE purchasetype_old")


def downgrade() -> None:
    op.execute("ALTER TYPE purchasetype RENAME TO purchasetype_new")
    op.execute(
        "CREATE TYPE purchasetype AS ENUM ('NEW', 'RENEW', 'CHANGE', 'ADDITIONAL')"
    )
    op.execute("""
        ALTER TABLE transactions
        ALTER COLUMN purchase_type TYPE purchasetype
        USING (
            CASE
                WHEN purchase_type::text = 'UPGRADE' THEN 'CHANGE'
                ELSE purchase_type::text
            END
        )::purchasetype
    """)
    op.execute("DROP TYPE purchasetype_new")
