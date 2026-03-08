"""Add web_accounts and auth_challenges tables for secure web auth flows.

Revision ID: 0030
Revises: 0029
Create Date: 2026-02-25 18:30:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0030"
down_revision: Union[str, None] = "0029"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "web_accounts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(), nullable=False),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column("email_normalized", sa.String(), nullable=True),
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("token_version", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("link_prompt_snooze_until", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["user_telegram_id"], ["users.telegram_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_telegram_id"),
        sa.UniqueConstraint("username"),
        sa.UniqueConstraint("email_normalized"),
    )
    op.create_index("ix_web_accounts_user_telegram_id", "web_accounts", ["user_telegram_id"])
    op.create_index("ix_web_accounts_username", "web_accounts", ["username"])
    op.create_index("ix_web_accounts_email_normalized", "web_accounts", ["email_normalized"])

    op.create_table(
        "auth_challenges",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("web_account_id", sa.Integer(), nullable=False),
        sa.Column("purpose", sa.String(), nullable=False),
        sa.Column("channel", sa.String(), nullable=False),
        sa.Column("destination", sa.String(), nullable=False),
        sa.Column("code_hash", sa.String(), nullable=True),
        sa.Column("token_hash", sa.String(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempts_left", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("meta", sa.JSON(), nullable=True),
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
        sa.ForeignKeyConstraint(["web_account_id"], ["web_accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_auth_challenges_web_account_id", "auth_challenges", ["web_account_id"])
    op.create_index("ix_auth_challenges_purpose", "auth_challenges", ["purpose"])
    op.create_index("ix_auth_challenges_destination", "auth_challenges", ["destination"])
    op.create_index(
        "ix_auth_challenges_purpose_destination_expires",
        "auth_challenges",
        ["purpose", "destination", "expires_at"],
    )
    op.create_index(
        "ix_auth_challenges_web_account_purpose_consumed",
        "auth_challenges",
        ["web_account_id", "purpose", "consumed_at"],
    )
    op.create_index("ix_auth_challenges_token_hash", "auth_challenges", ["token_hash"])

    # Backfill legacy users with auth credentials into new web_accounts table.
    op.execute(
        sa.text(
            """
            WITH candidates AS (
                SELECT
                    u.id,
                    u.telegram_id,
                    LOWER(u.auth_username) AS username,
                    u.password_hash,
                    ROW_NUMBER() OVER (PARTITION BY LOWER(u.auth_username) ORDER BY u.id ASC) AS rn
                FROM users u
                WHERE u.auth_username IS NOT NULL
                  AND u.password_hash IS NOT NULL
            )
            INSERT INTO web_accounts (
                user_telegram_id,
                username,
                password_hash,
                token_version
            )
            SELECT
                c.telegram_id,
                c.username,
                c.password_hash,
                0
            FROM candidates c
            WHERE c.rn = 1
            ON CONFLICT (user_telegram_id) DO NOTHING
            """
        )
    )


def downgrade() -> None:
    op.drop_index("ix_auth_challenges_token_hash", table_name="auth_challenges")
    op.drop_index(
        "ix_auth_challenges_web_account_purpose_consumed",
        table_name="auth_challenges",
    )
    op.drop_index(
        "ix_auth_challenges_purpose_destination_expires",
        table_name="auth_challenges",
    )
    op.drop_index("ix_auth_challenges_destination", table_name="auth_challenges")
    op.drop_index("ix_auth_challenges_purpose", table_name="auth_challenges")
    op.drop_index("ix_auth_challenges_web_account_id", table_name="auth_challenges")
    op.drop_table("auth_challenges")

    op.drop_index("ix_web_accounts_email_normalized", table_name="web_accounts")
    op.drop_index("ix_web_accounts_username", table_name="web_accounts")
    op.drop_index("ix_web_accounts_user_telegram_id", table_name="web_accounts")
    op.drop_table("web_accounts")
