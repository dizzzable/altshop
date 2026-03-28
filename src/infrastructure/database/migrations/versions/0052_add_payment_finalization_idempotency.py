"""Add payment finalization idempotency markers.

Revision ID: 0052
Revises: 0051
Create Date: 2026-03-28 18:20:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0052"
down_revision: Union[str, None] = "0051"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "transactions",
        sa.Column("discount_consumed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "transactions",
        sa.Column("test_notification_sent_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "transactions",
        sa.Column("subscription_notification_sent_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "transactions",
        sa.Column("subscription_purchase_enqueued_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.add_column(
        "referral_rewards",
        sa.Column("source_transaction_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_referral_rewards_source_transaction_id_transactions",
        "referral_rewards",
        "transactions",
        ["source_transaction_id"],
        ["id"],
        ondelete="SET NULL",
    )

    with op.get_context().autocommit_block():
        op.execute(
            "CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS "
            "ix_referral_rewards_source_transaction_unique "
            "ON referral_rewards (referral_id, user_telegram_id, source_transaction_id) "
            "WHERE source_transaction_id IS NOT NULL"
        )
        op.execute(
            "CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS "
            "ix_partner_transactions_source_transaction_unique "
            "ON partner_transactions "
            "(partner_id, referral_telegram_id, level, source_transaction_id) "
            "WHERE source_transaction_id IS NOT NULL"
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            "DROP INDEX CONCURRENTLY IF EXISTS "
            "ix_partner_transactions_source_transaction_unique"
        )
        op.execute(
            "DROP INDEX CONCURRENTLY IF EXISTS "
            "ix_referral_rewards_source_transaction_unique"
        )

    op.drop_constraint(
        "fk_referral_rewards_source_transaction_id_transactions",
        "referral_rewards",
        type_="foreignkey",
    )
    op.drop_column("referral_rewards", "source_transaction_id")

    op.drop_column("transactions", "subscription_purchase_enqueued_at")
    op.drop_column("transactions", "subscription_notification_sent_at")
    op.drop_column("transactions", "test_notification_sent_at")
    op.drop_column("transactions", "discount_consumed_at")
