"""Repair auth fields in users table if migration 0028 was stamped but not applied.

Revision ID: 0029
Revises: 0028
Create Date: 2026-02-22 12:36:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0029"
down_revision: Union[str, None] = "0028"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


USERS_TABLE = "users"
AUTH_USERNAME_COLUMN = "auth_username"
PASSWORD_HASH_COLUMN = "password_hash"
AUTH_USERNAME_INDEX = "ix_users_auth_username"


def _has_column(column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = inspector.get_columns(USERS_TABLE)
    return any(column.get("name") == column_name for column in columns)


def _has_index(index_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    indexes = inspector.get_indexes(USERS_TABLE)
    return any(index.get("name") == index_name for index in indexes)


def upgrade() -> None:
    # Some installations were stamped to 0028 without actually applying the DDL.
    # Keep this migration idempotent to repair such databases safely.
    if not _has_column(AUTH_USERNAME_COLUMN):
        op.add_column(USERS_TABLE, sa.Column(AUTH_USERNAME_COLUMN, sa.String(), nullable=True))

    if not _has_column(PASSWORD_HASH_COLUMN):
        op.add_column(USERS_TABLE, sa.Column(PASSWORD_HASH_COLUMN, sa.String(), nullable=True))

    if not _has_index(AUTH_USERNAME_INDEX):
        op.create_index(
            op.f(AUTH_USERNAME_INDEX),
            USERS_TABLE,
            [AUTH_USERNAME_COLUMN],
            unique=True,
        )


def downgrade() -> None:
    if _has_index(AUTH_USERNAME_INDEX):
        op.drop_index(op.f(AUTH_USERNAME_INDEX), table_name=USERS_TABLE)

    if _has_column(PASSWORD_HASH_COLUMN):
        op.drop_column(USERS_TABLE, PASSWORD_HASH_COLUMN)

    if _has_column(AUTH_USERNAME_COLUMN):
        op.drop_column(USERS_TABLE, AUTH_USERNAME_COLUMN)
