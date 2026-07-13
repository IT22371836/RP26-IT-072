from collections.abc import Callable, Coroutine
from typing import Annotated, Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import Settings, get_settings
from app.core.database import get_database
from app.core.security import InvalidAccessTokenError, decode_access_token
from app.repositories.providers import ProviderRepository
from app.repositories.service_requests import ServiceRequestRepository
from app.repositories.users import UserRepository
from app.schemas.auth import UserPublic
from app.schemas.common import UserRole

bearer_scheme = HTTPBearer(auto_error=False)


def get_user_repository(database: Annotated[Any, Depends(get_database)]) -> UserRepository:
    return UserRepository(database)


def get_provider_repository(database: Annotated[Any, Depends(get_database)]) -> ProviderRepository:
    return ProviderRepository(database)


def get_service_request_repository(
    database: Annotated[Any, Depends(get_database)],
) -> ServiceRequestRepository:
    return ServiceRequestRepository(database)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    repository: Annotated[UserRepository, Depends(get_user_repository)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> UserPublic:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing authentication token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized
    try:
        user_id, _ = decode_access_token(credentials.credentials, settings)
    except InvalidAccessTokenError as error:
        raise unauthorized from error

    document = await repository.find_by_id(user_id)
    if document is None or not document.get("is_active", True):
        raise unauthorized
    return UserPublic.model_validate(document)


def require_role(
    *allowed_roles: UserRole,
) -> Callable[[UserPublic], Coroutine[Any, Any, UserPublic]]:
    async def dependency(
        current_user: Annotated[UserPublic, Depends(get_current_user)],
    ) -> UserPublic:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user

    return dependency
