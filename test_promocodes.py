import asyncio
import sys
from pathlib import Path

# Add the src directory to the path
sys.path.append(str(Path(__file__).parent))

from src.core.config import load_config
from src.infrastructure.database import UnitOfWork
from src.services.promocode import PromocodeService


async def test_promocodes():
    config = load_config()
    uow = UnitOfWork(config.database)
    service = PromocodeService(config.app, None, None, None, None, uow)
    promos = await service.get_all()
    print(f'Found {len(promos)} promocodes')
    for p in promos:
        print(f'Code: {p.code}, Active: {p.is_active}, Type: {p.reward_type}, Expired: {p.is_expired}, Depleted: {p.is_depleted}')


if __name__ == "__main__":
    asyncio.run(test_promocodes())