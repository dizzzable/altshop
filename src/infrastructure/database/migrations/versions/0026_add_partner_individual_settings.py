"""Add individual_settings column to partners table."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0026"
down_revision: Union[str, None] = "0025"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Default individual settings JSON
DEFAULT_INDIVIDUAL_SETTINGS_JSON = '{"use_global_settings": true, "accrual_strategy": "ON_EACH_PAYMENT", "reward_type": "PERCENT", "level1_percent": null, "level2_percent": null, "level3_percent": null, "level1_fixed_amount": null, "level2_fixed_amount": null, "level3_fixed_amount": null}'


def upgrade() -> None:
    op.add_column(
        "partners",
        sa.Column(
            "individual_settings",
            sa.JSON(),
            nullable=False,
            server_default=sa.text(f"'{DEFAULT_INDIVIDUAL_SETTINGS_JSON}'::json"),
        ),
    )


def downgrade() -> None:
    op.drop_column("partners", "individual_settings")