"""Add additive indexes for current database hotspots.

Revision ID: 0051
Revises: 0050
Create Date: 2026-03-28 16:40:00.000000
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0051"
down_revision: Union[str, None] = "0050"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # PostgreSQL requires CONCURRENTLY indexes to run outside the revision transaction.
    with op.get_context().autocommit_block():
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_subscriptions_plan_id_expr "
            "ON subscriptions ((((plan ->> 'id')::integer)))"
        )
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS "
            "ix_transactions_user_telegram_id_created_at_desc "
            "ON transactions (user_telegram_id, created_at DESC)"
        )
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_transactions_status "
            "ON transactions (status)"
        )
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS "
            "ix_backup_records_backup_timestamp_created_at_id "
            "ON backup_records (backup_timestamp DESC NULLS LAST, created_at DESC, id DESC)"
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            "DROP INDEX CONCURRENTLY IF EXISTS "
            "ix_backup_records_backup_timestamp_created_at_id"
        )
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_transactions_status")
        op.execute(
            "DROP INDEX CONCURRENTLY IF EXISTS "
            "ix_transactions_user_telegram_id_created_at_desc"
        )
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_subscriptions_plan_id_expr")
