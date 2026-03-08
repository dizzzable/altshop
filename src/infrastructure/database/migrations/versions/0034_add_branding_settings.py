"""Add branding settings.

Revision ID: 0034
Revises: 0033
Create Date: 2026-02-28 18:10:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0034"
down_revision: Union[str, None] = "0033"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "settings",
        sa.Column(
            "branding",
            sa.JSON(),
            nullable=False,
            server_default=(
                '{"project_name":"AltShop","web_title":"AltShop - VPN Subscription Management",'
                '"bot_menu_button_text":"Shop","verification":{"telegram_template":{"ru":"{project_name} код '
                'верификации\\nКод: {code}\\n\\nВведите этот код в веб-профиле, чтобы связать Telegram.",'
                '"en":"{project_name} verification code\\nCode: {code}\\n\\nEnter this code in your web '
                'profile to link Telegram."},"web_request_delivered":{"ru":"Код верификации отправлен в '
                'Telegram","en":"Verification code sent to Telegram"},"web_request_open_bot":{"ru":"Код '
                'создан. Откройте чат с ботом, нажмите /start и повторите попытку","en":"Code generated. '
                'Open bot chat, press /start and retry"},"web_confirm_success":{"ru":"Telegram аккаунт '
                'успешно привязан","en":"Telegram account linked successfully"}}}'
            ),
        ),
    )


def downgrade() -> None:
    op.drop_column("settings", "branding")
