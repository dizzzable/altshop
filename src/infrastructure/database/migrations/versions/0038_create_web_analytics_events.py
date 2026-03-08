"""Create web_analytics_events table."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0038"
down_revision: Union[str, None] = "0037"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "web_analytics_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("timezone('UTC', now())"),
            nullable=False,
        ),
        sa.Column("event_name", sa.String(length=128), nullable=False),
        sa.Column("source_path", sa.String(length=255), nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("user_telegram_id", sa.BigInteger(), nullable=True),
        sa.Column("device_mode", sa.String(length=32), nullable=False),
        sa.Column("is_in_telegram", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("has_init_data", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("start_param", sa.String(length=128), nullable=True),
        sa.Column("has_query_id", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("chat_type", sa.String(length=64), nullable=True),
        sa.Column(
            "meta",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index("ix_web_analytics_events_created_at", "web_analytics_events", ["created_at"])
    op.create_index(
        "ix_web_analytics_events_event_name_created_at",
        "web_analytics_events",
        ["event_name", "created_at"],
    )
    op.create_index(
        "ix_web_analytics_events_session_id_created_at",
        "web_analytics_events",
        ["session_id", "created_at"],
    )
    op.create_index(
        "ix_web_analytics_events_user_telegram_id_created_at",
        "web_analytics_events",
        ["user_telegram_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_web_analytics_events_user_telegram_id_created_at",
        table_name="web_analytics_events",
    )
    op.drop_index(
        "ix_web_analytics_events_session_id_created_at",
        table_name="web_analytics_events",
    )
    op.drop_index(
        "ix_web_analytics_events_event_name_created_at",
        table_name="web_analytics_events",
    )
    op.drop_index("ix_web_analytics_events_created_at", table_name="web_analytics_events")
    op.drop_table("web_analytics_events")
