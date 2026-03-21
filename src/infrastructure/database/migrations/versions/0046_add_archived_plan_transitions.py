"""Add archived plan lifecycle and transition settings.

Revision ID: 0046
Revises: 0045
Create Date: 2026-03-21 13:40:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0046"
down_revision: Union[str, None] = "0045"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    archived_plan_renew_mode = sa.Enum(
        "SELF_RENEW",
        "REPLACE_ON_RENEW",
        name="archived_plan_renew_mode",
    )
    archived_plan_renew_mode.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "plans",
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "plans",
        sa.Column(
            "archived_renew_mode",
            archived_plan_renew_mode,
            nullable=False,
            server_default="SELF_RENEW",
        ),
    )
    op.add_column(
        "plans",
        sa.Column(
            "replacement_plan_ids",
            postgresql.ARRAY(sa.Integer()),
            nullable=False,
            server_default=sa.text("'{}'::integer[]"),
        ),
    )
    op.add_column(
        "plans",
        sa.Column(
            "upgrade_to_plan_ids",
            postgresql.ARRAY(sa.Integer()),
            nullable=False,
            server_default=sa.text("'{}'::integer[]"),
        ),
    )

    op.execute(
        """
        UPDATE plans
        SET upgrade_to_plan_ids = COALESCE(
            (
                SELECT array_agg(target.id ORDER BY target.order_index)
                FROM plans AS target
                WHERE target.is_active = TRUE
                  AND target.is_archived = FALSE
                  AND target.availability <> 'TRIAL'
                  AND target.id <> plans.id
            ),
            '{}'::integer[]
        )
        WHERE availability = 'TRIAL'
        """
    )

    op.alter_column("plans", "is_archived", server_default=None)
    op.alter_column("plans", "archived_renew_mode", server_default=None)
    op.alter_column("plans", "replacement_plan_ids", server_default=None)
    op.alter_column("plans", "upgrade_to_plan_ids", server_default=None)


def downgrade() -> None:
    op.drop_column("plans", "upgrade_to_plan_ids")
    op.drop_column("plans", "replacement_plan_ids")
    op.drop_column("plans", "archived_renew_mode")
    op.drop_column("plans", "is_archived")

    archived_plan_renew_mode = sa.Enum(
        "SELF_RENEW",
        "REPLACE_ON_RENEW",
        name="archived_plan_renew_mode",
    )
    archived_plan_renew_mode.drop(op.get_bind(), checkfirst=True)
