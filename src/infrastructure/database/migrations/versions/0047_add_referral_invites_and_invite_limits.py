"""Add referral invites and invite-limit settings.

Revision ID: 0047
Revises: 0046
Create Date: 2026-03-22 11:30:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0047"
down_revision: Union[str, None] = "0046"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DEFAULT_REFERRAL_INVITE_SETTINGS_JSON = (
    '{"use_global_settings": true, "link_ttl_enabled": false, '
    '"link_ttl_seconds": null, "slots_enabled": false, "initial_slots": null, '
    '"refill_threshold_qualified": null, "refill_amount": null}'
)

DEFAULT_REFERRAL_INVITE_LIMITS_JSON = (
    '{"link_ttl_enabled": false, "link_ttl_seconds": null, '
    '"slots_enabled": false, "initial_slots": null, '
    '"refill_threshold_qualified": null, "refill_amount": null}'
)


def upgrade() -> None:
    op.create_table(
        "referral_invites",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "inviter_telegram_id",
            sa.BigInteger(),
            sa.ForeignKey("users.telegram_id"),
            nullable=False,
        ),
        sa.Column("token", sa.String(), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("TIMEZONE('utc', NOW())"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("TIMEZONE('utc', NOW())"),
        ),
    )
    op.create_index(
        "ix_referral_invites_inviter_telegram_id",
        "referral_invites",
        ["inviter_telegram_id"],
        unique=False,
    )

    op.add_column(
        "users",
        sa.Column(
            "referral_invite_settings",
            sa.JSON(),
            nullable=False,
            server_default=sa.text(f"'{DEFAULT_REFERRAL_INVITE_SETTINGS_JSON}'::json"),
        ),
    )

    op.execute(
        f"""
        UPDATE settings
        SET referral = (
            referral::jsonb || '{{"invite_limits": {DEFAULT_REFERRAL_INVITE_LIMITS_JSON}}}'::jsonb
        )::json
        WHERE referral IS NOT NULL
          AND NOT (referral::jsonb ? 'invite_limits')
        """
    )

    op.alter_column("users", "referral_invite_settings", server_default=None)


def downgrade() -> None:
    op.drop_column("users", "referral_invite_settings")
    op.drop_index("ix_referral_invites_inviter_telegram_id", table_name="referral_invites")
    op.drop_table("referral_invites")

    op.execute(
        """
        UPDATE settings
        SET referral = (referral::jsonb - 'invite_limits')::json
        WHERE referral IS NOT NULL
          AND (referral::jsonb ? 'invite_limits')
        """
    )
