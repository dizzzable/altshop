import asyncio
import sys
from pathlib import Path

# Add the src directory to the path
sys.path.append(str(Path(__file__).parent))

from sqlalchemy.ext.asyncio import create_async_engine
from src.core.config.app import AppConfig
from src.infrastructure.database import UnitOfWork
from src.infrastructure.database.repositories import RepositoriesFacade
from src.services.promocode import PromocodeService


async def test_promocodes():
    config = AppConfig.get()
    
    # Create async engine and session pool
    engine = create_async_engine(
        config.database.dsn,
        echo=config.database.echo,
        pool_size=config.database.pool_size,
        max_overflow=config.database.max_overflow,
        pool_timeout=config.database.pool_timeout,
        pool_recycle=config.database.pool_recycle,
    )
    
    from sqlalchemy.ext.asyncio import async_sessionmaker
    session_pool = async_sessionmaker(engine, expire_on_commit=False)
    
    # Create UOW instance
    uow = UnitOfWork(session_pool)
    
    # Initialize the service with minimal required parameters
    service = PromocodeService(
        config=config,
        bot=None,
        redis_client=None,
        redis_repository=None,
        translator_hub=None,
        uow=uow
    )
    
    # Use the UOW properly with async context manager
    async with uow:
        promos = await uow.repository.promocodes.get_all()
        print(f'Found {len(promos)} promocodes')
        for p in promos:
            print(f'Code: {p.code}, Active: {p.is_active}, Type: {p.reward_type}, Expired: {p.is_expired}, Depleted: {p.is_depleted}')


if __name__ == "__main__":
    asyncio.run(test_promocodes())