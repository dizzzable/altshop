from types import TracebackType
from typing import AsyncContextManager, Optional, Self, Type

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .repositories import RepositoriesFacade


class UnitOfWork:
    session_pool: async_sessionmaker[AsyncSession]
    session: Optional[AsyncSession] = None

    repository: RepositoriesFacade

    def __init__(self, session_pool: async_sessionmaker[AsyncSession]) -> None:
        self.session_pool = session_pool
        self._session_ctx: Optional[AsyncContextManager[AsyncSession]] = None
        self._context_depth = 0

    async def __aenter__(self) -> Self:
        if self.session is not None:
            self._context_depth += 1
            return self

        self._session_ctx = self.session_pool()
        self.session = await self._session_ctx.__aenter__()
        self.repository = RepositoriesFacade(session=self.session)
        self._context_depth = 1
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        if self.session is None:
            return

        self._context_depth = max(self._context_depth - 1, 0)
        if self._context_depth > 0:
            return

        try:
            if exc_type is None:
                await self.commit()
            else:
                logger.warning(f"Exception detected ({exc_val}), rolling back session")
                await self.rollback()
        finally:
            await self._close_session(exc_type, exc_val, exc_tb)

    async def commit(self) -> None:
        if self.session:
            await self.session.commit()

    async def rollback(self) -> None:
        if self.session:
            await self.session.rollback()
            logger.debug("Session rolled back")

    async def _close_session(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        if self._session_ctx is not None:
            await self._session_ctx.__aexit__(exc_type, exc_val, exc_tb)
        elif self.session is not None:
            await self.session.close()

        self.session = None
        self._session_ctx = None
