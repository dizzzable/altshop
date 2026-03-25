"""Add bot menu settings.

Revision ID: 0049
Revises: 0048
Create Date: 2026-03-25 15:15:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0049"
down_revision: Union[str, None] = "0048"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DEFAULT_BOT_MENU_SETTINGS_JSON = (
    '{"miniapp_only_enabled": false, "mini_app_url": null, "custom_buttons": []}'
)


def upgrade() -> None:
    op.add_column(
        "settings",
        sa.Column(
            "bot_menu",
            sa.JSON(),
            nullable=False,
            server_default=DEFAULT_BOT_MENU_SETTINGS_JSON,
        ),
    )


def downgrade() -> None:
    op.drop_column("settings", "bot_menu")
