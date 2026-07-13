from typing import Any

from app.repositories.providers import ProviderRepository
from app.repositories.service_requests import ServiceRequestRepository
from app.repositories.users import UserRepository


async def ensure_application_indexes(database: Any) -> None:
    await UserRepository(database).ensure_indexes()
    await ProviderRepository(database).ensure_indexes()
    await ServiceRequestRepository(database).ensure_indexes()
