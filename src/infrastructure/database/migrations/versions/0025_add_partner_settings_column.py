"""Add partner column to settings table."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0025"
down_revision: Union[str, None] = "0024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Default partner settings JSON
DEFAULT_PARTNER_SETTINGS_JSON = '{"enabled": false, "level1_percent": "10.0", "level2_percent": "3.0", "level3_percent": "1.0", "tax_percent": "6.0", "yookassa_commission": "3.5", "telegram_stars_commission": "30.0", "cryptopay_commission": "1.0", "heleket_commission": "1.0", "pal24_commission": "5.0", "wata_commission": "3.0", "platega_commission": "3.5", "min_withdrawal_amount": 50000, "auto_calculate_commission": true}'


def upgrade() -> None:
    op.add_column(
        "settings",
        sa.Column(
            "partner",
            sa.JSON(),
            nullable=False,
            server_default=sa.text(f"'{DEFAULT_PARTNER_SETTINGS_JSON}'::json"),
        ),
    )


def downgrade() -> None:
    op.drop_column("settings", "partner")