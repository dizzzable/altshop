"""Create partner tables for affiliate program."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0024"
down_revision: Union[str, None] = "0023"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create partner_level enum
    partner_level_enum = postgresql.ENUM(
        "LEVEL_1",
        "LEVEL_2",
        "LEVEL_3",
        name="partner_level",
    )
    partner_level_enum.create(op.get_bind(), checkfirst=True)

    # Create partners table
    op.create_table(
        "partners",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("balance", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_earned", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_withdrawn", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("referrals_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("level2_referrals_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("level3_referrals_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("timezone('UTC', now())"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("timezone('UTC', now())"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_telegram_id"],
            ["users.telegram_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_telegram_id"),
    )

    # Create partner_transactions table
    op.create_table(
        "partner_transactions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("partner_id", sa.Integer(), nullable=False),
        sa.Column("referral_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "level",
            postgresql.ENUM(name="partner_level", create_type=False),
            nullable=False,
        ),
        sa.Column("payment_amount", sa.Integer(), nullable=False),
        sa.Column("percent", sa.Numeric(5, 2), nullable=False),
        sa.Column("earned_amount", sa.Integer(), nullable=False),
        sa.Column("source_transaction_id", sa.Integer(), nullable=True),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("timezone('UTC', now())"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("timezone('UTC', now())"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["partner_id"],
            ["partners.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["referral_telegram_id"],
            ["users.telegram_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create partner_withdrawals table
    op.create_table(
        "partner_withdrawals",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("partner_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("method", sa.String(), nullable=False),
        sa.Column("requisites", sa.String(), nullable=False),
        sa.Column("admin_comment", sa.String(), nullable=True),
        sa.Column("processed_by", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("timezone('UTC', now())"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("timezone('UTC', now())"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["partner_id"],
            ["partners.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create partner_referrals table
    op.create_table(
        "partner_referrals",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("partner_id", sa.Integer(), nullable=False),
        sa.Column("referral_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "level",
            postgresql.ENUM(name="partner_level", create_type=False),
            nullable=False,
        ),
        sa.Column("parent_partner_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("timezone('UTC', now())"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("timezone('UTC', now())"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["partner_id"],
            ["partners.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["referral_telegram_id"],
            ["users.telegram_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["parent_partner_id"],
            ["partners.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes
    op.create_index(
        "ix_partners_user_telegram_id",
        "partners",
        ["user_telegram_id"],
    )
    op.create_index(
        "ix_partner_transactions_partner_id",
        "partner_transactions",
        ["partner_id"],
    )
    op.create_index(
        "ix_partner_withdrawals_partner_id",
        "partner_withdrawals",
        ["partner_id"],
    )
    op.create_index(
        "ix_partner_referrals_partner_id",
        "partner_referrals",
        ["partner_id"],
    )
    op.create_index(
        "ix_partner_referrals_referral_telegram_id",
        "partner_referrals",
        ["referral_telegram_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_partner_referrals_referral_telegram_id", table_name="partner_referrals")
    op.drop_index("ix_partner_referrals_partner_id", table_name="partner_referrals")
    op.drop_index("ix_partner_withdrawals_partner_id", table_name="partner_withdrawals")
    op.drop_index("ix_partner_transactions_partner_id", table_name="partner_transactions")
    op.drop_index("ix_partners_user_telegram_id", table_name="partners")

    op.drop_table("partner_referrals")
    op.drop_table("partner_withdrawals")
    op.drop_table("partner_transactions")
    op.drop_table("partners")

    # Drop enum
    partner_level_enum = postgresql.ENUM(
        "LEVEL_1",
        "LEVEL_2",
        "LEVEL_3",
        name="partner_level",
    )
    partner_level_enum.drop(op.get_bind(), checkfirst=True)