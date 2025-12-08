import asyncio
import sys
from pathlib import Path

# Add the src directory to the path
sys.path.append(str(Path(__file__).parent))

from sqlalchemy.ext.asyncio import create_async_engine
from src.core.config.app import AppConfig
from src.infrastructure.database import UnitOfWork
from src.services.plan import PlanService


async def test_plans():
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
    service = PlanService(
        config=config,
        bot=None,
        redis_client=None,
        redis_repository=None,
        translator_hub=None,
        uow=uow
    )
    
    # Use the UOW properly with async context manager
    async with uow:
        plans = await uow.repository.plans.get_all()
        print(f'Found {len(plans)} plans')
        for p in plans:
            print(f'Name: {p.name}, Active: {p.is_active}, Type: {p.type}, Traffic: {p.traffic_limit}, Devices: {p.device_limit}')


if __name__ == "__main__":
    asyncio.run(test_plans())