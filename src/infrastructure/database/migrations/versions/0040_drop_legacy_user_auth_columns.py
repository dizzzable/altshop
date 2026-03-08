"""Drop legacy auth columns from users.

Revision ID: 0040
Revises: 0039
Create Date: 2026-03-07 00:30:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0040"
down_revision: Union[str, None] = "0039"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


USERS_TABLE = "users"
WEB_ACCOUNTS_TABLE = "web_accounts"
AUTH_USERNAME_COLUMN = "auth_username"
PASSWORD_HASH_COLUMN = "password_hash"
AUTH_USERNAME_INDEX = "ix_users_auth_username"


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = inspector.get_columns(table_name)
    return any(column.get("name") == column_name for column in columns)


def _has_index(table_name: str, index_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    indexes = inspector.get_indexes(table_name)
    return any(index.get("name") == index_name for index in indexes)


def upgrade() -> None:
    if _has_index(USERS_TABLE, AUTH_USERNAME_INDEX):
        op.drop_index(op.f(AUTH_USERNAME_INDEX), table_name=USERS_TABLE)

    if _has_column(USERS_TABLE, PASSWORD_HASH_COLUMN):
        op.drop_column(USERS_TABLE, PASSWORD_HASH_COLUMN)

    if _has_column(USERS_TABLE, AUTH_USERNAME_COLUMN):
        op.drop_column(USERS_TABLE, AUTH_USERNAME_COLUMN)


def downgrade() -> None:
    if not _has_column(USERS_TABLE, AUTH_USERNAME_COLUMN):
        op.add_column(USERS_TABLE, sa.Column(AUTH_USERNAME_COLUMN, sa.String(), nullable=True))

    if not _has_column(USERS_TABLE, PASSWORD_HASH_COLUMN):
        op.add_column(USERS_TABLE, sa.Column(PASSWORD_HASH_COLUMN, sa.String(), nullable=True))

    op.execute(
        sa.text(
            """
            UPDATE users AS u
            SET
                auth_username = wa.username,
                password_hash = wa.password_hash
            FROM web_accounts AS wa
            WHERE u.telegram_id = wa.user_telegram_id
              AND (
                    u.auth_username IS DISTINCT FROM wa.username
                 OR u.password_hash IS DISTINCT FROM wa.password_hash
              )
            """
        )
    )

    if not _has_index(USERS_TABLE, AUTH_USERNAME_INDEX):
        op.create_index(
            op.f(AUTH_USERNAME_INDEX),
            USERS_TABLE,
            [AUTH_USERNAME_COLUMN],
            unique=True,
        )
