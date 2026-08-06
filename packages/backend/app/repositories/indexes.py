from typing import Any

from app.repositories.component1 import Component1Repository
from app.repositories.component4 import Component4Repository
from app.repositories.customers import CustomerProfileRepository
from app.repositories.interactions import InteractionRepository
from app.repositories.providers import ProviderRepository
from app.repositories.service_requests import ServiceRequestRepository
from app.repositories.users import UserRepository


async def ensure_application_indexes(database: Any) -> None:
    await UserRepository(database).ensure_indexes()
    await ProviderRepository(database).ensure_indexes()
    await CustomerProfileRepository(database).ensure_indexes()
    await InteractionRepository(database).ensure_indexes()
    await ServiceRequestRepository(database).ensure_indexes()
    await Component1Repository(database).ensure_indexes()
    await Component4Repository(database).ensure_indexes()
