from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from app.api.dependencies import (
    get_interaction_repository,
    get_provider_repository,
    get_service_request_repository,
    get_user_repository,
    require_role,
)
from app.repositories.interactions import InteractionRepository
from app.repositories.providers import ProviderRepository
from app.repositories.service_requests import ServiceRequestRepository
from app.repositories.users import UserRepository
from app.schemas.auth import UserPublic
from app.schemas.common import UserRole
from app.schemas.provider import ProviderPublic
from app.schemas.service_request import ServiceRequestPublic

router = APIRouter(prefix="/admin", tags=["administration"])
admin_user = require_role(UserRole.ADMIN)


class AdminOverview(BaseModel):
    users: int
    providers: int
    service_requests: int
    interactions: int


class UserStatusUpdate(BaseModel):
    is_active: bool


@router.get("/overview", response_model=AdminOverview)
async def overview(
    _: Annotated[UserPublic, Depends(admin_user)],
    users: Annotated[UserRepository, Depends(get_user_repository)],
    providers: Annotated[ProviderRepository, Depends(get_provider_repository)],
    requests: Annotated[ServiceRequestRepository, Depends(get_service_request_repository)],
    interactions: Annotated[InteractionRepository, Depends(get_interaction_repository)],
) -> AdminOverview:
    return AdminOverview(
        users=await users.count(),
        providers=await providers.count(),
        service_requests=await requests.count(),
        interactions=await interactions.count(),
    )


@router.get("/users", response_model=list[UserPublic])
async def list_users(
    _: Annotated[UserPublic, Depends(admin_user)],
    repository: Annotated[UserRepository, Depends(get_user_repository)],
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
) -> list[UserPublic]:
    return [UserPublic.model_validate(record) for record in await repository.list_all(limit)]


@router.patch("/users/{user_id}/status", response_model=UserPublic)
async def update_user_status(
    user_id: str,
    payload: UserStatusUpdate,
    current_user: Annotated[UserPublic, Depends(admin_user)],
    repository: Annotated[UserRepository, Depends(get_user_repository)],
) -> UserPublic:
    if user_id == current_user.user_id and not payload.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="You cannot deactivate your own account"
        )
    record = await repository.set_active(user_id, payload.is_active)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return UserPublic.model_validate(record)


@router.get("/providers", response_model=list[ProviderPublic])
async def list_providers(
    _: Annotated[UserPublic, Depends(admin_user)],
    repository: Annotated[ProviderRepository, Depends(get_provider_repository)],
) -> list[ProviderPublic]:
    return [ProviderPublic.model_validate(record) for record in await repository.list_all(500)]


@router.get("/service-requests", response_model=list[ServiceRequestPublic])
async def list_requests(
    _: Annotated[UserPublic, Depends(admin_user)],
    repository: Annotated[ServiceRequestRepository, Depends(get_service_request_repository)],
) -> list[ServiceRequestPublic]:
    return [
        ServiceRequestPublic.model_validate(record) for record in await repository.list_all(500)
    ]
