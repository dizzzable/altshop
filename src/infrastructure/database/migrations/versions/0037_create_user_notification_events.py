"""Create user_notification_events table."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0037"
down_revision: Union[str, None] = "0036"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_notification_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("ntf_type", sa.String(length=128), nullable=False),
        sa.Column("i18n_key", sa.String(length=255), nullable=False),
        sa.Column(
            "i18n_kwargs",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("rendered_text", sa.Text(), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("read_source", sa.String(length=32), nullable=True),
        sa.Column("bot_chat_id", sa.BigInteger(), nullable=True),
        sa.Column("bot_message_id", sa.Integer(), nullable=True),
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
    )

    op.create_index(
        "ix_user_notification_events_user_created",
        "user_notification_events",
        ["user_telegram_id", "created_at"],
    )
    op.create_index(
        "ix_user_notification_events_user_read_created",
        "user_notification_events",
        ["user_telegram_id", "is_read", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_user_notification_events_user_read_created",
        table_name="user_notification_events",
    )
    op.drop_index(
        "ix_user_notification_events_user_created",
        table_name="user_notification_events",
    )
    op.drop_table("user_notification_events")
