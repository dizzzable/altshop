"""Add auth_username and password_hash to users

Revision ID: 0028
Revises: 0027
Create Date: 2024-02-19 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0028"
down_revision: Union[str, None] = "0027"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add auth_username column
    op.add_column("users", sa.Column("auth_username", sa.String(), nullable=True))

    # Add password_hash column
    op.add_column("users", sa.Column("password_hash", sa.String(), nullable=True))

    # Create unique index on auth_username
    op.create_index(op.f("ix_users_auth_username"), "users", ["auth_username"], unique=True)


def downgrade() -> None:
    # Drop index
    op.drop_index(op.f("ix_users_auth_username"), table_name="users")

    # Drop columns
    op.drop_column("users", "password_hash")
    op.drop_column("users", "auth_username")
