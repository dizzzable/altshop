"""Add web password reset flags to web_accounts.

Revision ID: 0036
Revises: 0035
Create Date: 2026-03-02 12:30:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0036"
down_revision: Union[str, None] = "0035"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "web_accounts",
        sa.Column(
            "requires_password_change",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "web_accounts",
        sa.Column(
            "temporary_password_expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("web_accounts", "temporary_password_expires_at")
    op.drop_column("web_accounts", "requires_password_change")
