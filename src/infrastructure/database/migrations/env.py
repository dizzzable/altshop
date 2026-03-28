import asyncio
from logging.config import fileConfig
from typing import Iterable, Optional, Union

from alembic import context
from alembic.operations import MigrationScript
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy.engine import Connection
from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from src.core.config import AppConfig
from src.infrastructure.database.models.sql import BaseSql

config = context.config
app_config = AppConfig.get()
db_config = app_config.database

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = BaseSql.metadata


def process_revision_directives(
    context: MigrationContext,
    revision: Union[str, Iterable[Optional[str]], Iterable[str]],
    directives: list[MigrationScript],
) -> None:
    migration_script = directives[0]

    script_directory = ScriptDirectory.from_config(config)
    head_revision = script_directory.get_current_head()

    if head_revision is None:
        new_rev_id = 1
    else:
        last_rev_id = int(head_revision.lstrip("0"))
        new_rev_id = last_rev_id + 1

    migration_script.rev_id = f"{new_rev_id:04}"


def _get_offline_migration_url() -> str:
    # Offline SQL rendering only needs the backend dialect, not the async driver.
    url = make_url(db_config.dsn)
    return url.set(drivername=url.drivername.split("+", maxsplit=1)[0]).render_as_string(
        hide_password=False
    )


def run_migrations_offline() -> None:
    context.configure(
        url=_get_offline_migration_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        transaction_per_migration=True,
        process_revision_directives=process_revision_directives,
        crypt_key=app_config.crypt_key.get_secret_value(),
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        transaction_per_migration=True,
        process_revision_directives=process_revision_directives,
        crypt_key=app_config.crypt_key.get_secret_value(),
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable: AsyncEngine = create_async_engine(url=db_config.dsn)

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
