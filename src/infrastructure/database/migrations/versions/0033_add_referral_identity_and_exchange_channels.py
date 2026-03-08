"""Add unified referral identity fields and transaction purchase channel.

Revision ID: 0033
Revises: 0032
Create Date: 2026-02-27 12:30:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0033"
down_revision: Union[str, None] = "0032"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'purchasechannel') THEN
                CREATE TYPE purchasechannel AS ENUM ('WEB', 'TELEGRAM');
            END IF;
        END
        $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'referral_invite_source') THEN
                CREATE TYPE referral_invite_source AS ENUM ('BOT', 'WEB', 'UNKNOWN');
            END IF;
        END
        $$;
        """
    )

    op.add_column(
        "transactions",
        sa.Column(
            "channel",
            postgresql.ENUM(name="purchasechannel", create_type=False),
            nullable=True,
        ),
    )

    op.add_column(
        "referrals",
        sa.Column(
            "invite_source",
            postgresql.ENUM(name="referral_invite_source", create_type=False),
            nullable=False,
            server_default="UNKNOWN",
        ),
    )
    op.add_column(
        "referrals",
        sa.Column("qualified_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "referrals",
        sa.Column(
            "qualified_purchase_channel",
            postgresql.ENUM(name="purchasechannel", create_type=False),
            nullable=True,
        ),
    )
    op.add_column(
        "referrals",
        sa.Column("qualified_transaction_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_referrals_qualified_transaction_id_transactions",
        "referrals",
        "transactions",
        ["qualified_transaction_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.alter_column("referrals", "invite_source", server_default=None)

    op.execute(
        sa.text(
            """
            WITH ranked AS (
                SELECT
                    r.id,
                    r.referred_telegram_id,
                    ROW_NUMBER() OVER (
                        PARTITION BY r.referred_telegram_id
                        ORDER BY r.created_at ASC, r.id ASC
                    ) AS row_num,
                    FIRST_VALUE(r.id) OVER (
                        PARTITION BY r.referred_telegram_id
                        ORDER BY r.created_at ASC, r.id ASC
                    ) AS keep_id
                FROM referrals r
            ),
            duplicates AS (
                SELECT id, keep_id
                FROM ranked
                WHERE row_num > 1
            )
            UPDATE referral_rewards rr
            SET referral_id = d.keep_id
            FROM duplicates d
            WHERE rr.referral_id = d.id
            """
        )
    )
    op.execute(
        sa.text(
            """
            WITH ranked AS (
                SELECT
                    r.id,
                    ROW_NUMBER() OVER (
                        PARTITION BY r.referred_telegram_id
                        ORDER BY r.created_at ASC, r.id ASC
                    ) AS row_num
                FROM referrals r
            )
            DELETE FROM referrals r
            USING ranked d
            WHERE r.id = d.id
              AND d.row_num > 1
            """
        )
    )

    op.create_unique_constraint(
        "uq_referrals_referred_telegram_id",
        "referrals",
        ["referred_telegram_id"],
    )
    op.create_index(
        "ix_referrals_referrer_telegram_id_created_at",
        "referrals",
        ["referrer_telegram_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_referrals_invite_source",
        "referrals",
        ["invite_source"],
        unique=False,
    )
    op.create_index(
        "ix_referrals_qualified_at",
        "referrals",
        ["qualified_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_referrals_qualified_at", table_name="referrals")
    op.drop_index("ix_referrals_invite_source", table_name="referrals")
    op.drop_index("ix_referrals_referrer_telegram_id_created_at", table_name="referrals")

    op.drop_constraint(
        "uq_referrals_referred_telegram_id",
        "referrals",
        type_="unique",
    )
    op.drop_constraint(
        "fk_referrals_qualified_transaction_id_transactions",
        "referrals",
        type_="foreignkey",
    )
    op.drop_column("referrals", "qualified_transaction_id")
    op.drop_column("referrals", "qualified_purchase_channel")
    op.drop_column("referrals", "qualified_at")
    op.drop_column("referrals", "invite_source")

    op.drop_column("transactions", "channel")

    op.execute("DROP TYPE IF EXISTS referral_invite_source")
    op.execute("DROP TYPE IF EXISTS purchasechannel")
