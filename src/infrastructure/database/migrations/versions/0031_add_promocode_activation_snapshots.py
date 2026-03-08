"""Add snapshot fields for promocode activations history.

Revision ID: 0031
Revises: 0030
Create Date: 2026-02-25 21:45:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0031"
down_revision: Union[str, None] = "0030"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "promocode_activations",
        sa.Column("promocode_code", sa.String(), nullable=True),
    )
    op.add_column(
        "promocode_activations",
        sa.Column(
            "reward_type",
            postgresql.ENUM(name="promocode_reward_type", create_type=False),
            nullable=True,
        ),
    )
    op.add_column(
        "promocode_activations",
        sa.Column("reward_value", sa.Integer(), nullable=True, server_default=sa.text("0")),
    )
    op.add_column(
        "promocode_activations",
        sa.Column("target_subscription_id", sa.Integer(), nullable=True),
    )

    op.create_foreign_key(
        "fk_promocode_activations_target_subscription_id_subscriptions",
        "promocode_activations",
        "subscriptions",
        ["target_subscription_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.execute(
        sa.text(
            """
            UPDATE promocode_activations pa
            SET
                promocode_code = p.code,
                reward_type = p.reward_type,
                reward_value = COALESCE(p.reward, 0)
            FROM promocodes p
            WHERE p.id = pa.promocode_id
            """
        )
    )

    op.alter_column("promocode_activations", "promocode_code", nullable=False)
    op.alter_column("promocode_activations", "reward_type", nullable=False)
    op.alter_column("promocode_activations", "reward_value", nullable=False, server_default=None)

    op.create_index(
        "ix_promocode_activations_user_telegram_id_activated_at",
        "promocode_activations",
        ["user_telegram_id", "activated_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_promocode_activations_user_telegram_id_activated_at",
        table_name="promocode_activations",
    )

    op.drop_constraint(
        "fk_promocode_activations_target_subscription_id_subscriptions",
        "promocode_activations",
        type_="foreignkey",
    )
    op.drop_column("promocode_activations", "target_subscription_id")
    op.drop_column("promocode_activations", "reward_value")
    op.drop_column("promocode_activations", "reward_type")
    op.drop_column("promocode_activations", "promocode_code")
