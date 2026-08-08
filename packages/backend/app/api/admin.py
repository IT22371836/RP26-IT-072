from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field, field_validator

from app.api.dependencies import (
    get_interaction_repository,
    get_provider_repository,
    get_service_request_repository,
    get_user_repository,
    require_role,
)
from app.api.providers import (
    document_storage_service,
    find_active_document,
    private_document_response,
)
from app.repositories.interactions import InteractionRepository
from app.repositories.providers import ProviderRepository
from app.repositories.service_requests import ServiceRequestRepository
from app.repositories.users import UserRepository
from app.schemas.auth import UserPublic
from app.schemas.common import UserRole
from app.schemas.provider import ProviderDocumentCategory, ProviderPrivate
from app.schemas.service_request import ServiceRequestPublic
from app.services.file_storage import FirebaseDocumentStorage

router = APIRouter(prefix="/admin", tags=["administration"])
admin_user = require_role(UserRole.ADMIN)


class AdminOverview(BaseModel):
    users: int
    providers: int
    service_requests: int
    interactions: int


class UserStatusUpdate(BaseModel):
    is_active: bool


class ProviderVerificationUpdate(BaseModel):
    verified: bool
    reason: str | None = Field(default=None, max_length=500)

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split())
        return normalized or None


class ProviderVerificationEventPublic(BaseModel):
    event_id: str
    provider_id: str
    admin_user_id: str
    previous_verified: bool
    verified: bool
    reason: str | None
    created_at: datetime


def active_document_count(document: dict) -> int:
    documents = document.get("documents")
    if not isinstance(documents, dict):
        return 0
    return sum(
        1
        for category in ProviderDocumentCategory
        for item in documents.get(category.value, [])
        if isinstance(item, dict) and item.get("deleted_at") is None
    )


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


@router.get("/providers", response_model=list[ProviderPrivate])
async def list_providers(
    _: Annotated[UserPublic, Depends(admin_user)],
    repository: Annotated[ProviderRepository, Depends(get_provider_repository)],
    users: Annotated[UserRepository, Depends(get_user_repository)],
) -> list[ProviderPrivate]:
    providers = await repository.list_all(500)
    results: list[ProviderPrivate] = []
    for record in providers:
        user = await users.find_by_id(str(record["user_id"]))
        enriched = {**record, "email": user.get("email") if user else None}
        results.append(ProviderPrivate.model_validate(enriched))
    return results


@router.get("/providers/{provider_id}/documents/{category}/{file_id}/content")
async def download_provider_document_for_review(
    provider_id: str,
    category: ProviderDocumentCategory,
    file_id: str,
    _: Annotated[UserPublic, Depends(admin_user)],
    repository: Annotated[ProviderRepository, Depends(get_provider_repository)],
    storage: Annotated[FirebaseDocumentStorage, Depends(document_storage_service)],
) -> Response:
    provider = await repository.find_by_id(provider_id)
    if provider is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")
    item = find_active_document(provider, category, file_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return await private_document_response(item, storage)


@router.patch("/providers/{provider_id}/verification", response_model=ProviderPrivate)
async def update_provider_verification(
    provider_id: str,
    payload: ProviderVerificationUpdate,
    current_user: Annotated[UserPublic, Depends(admin_user)],
    repository: Annotated[ProviderRepository, Depends(get_provider_repository)],
) -> ProviderPrivate:
    existing = await repository.find_by_id(provider_id)
    if existing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")
    if payload.verified and active_document_count(existing) == 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="At least one active provider document is required for verification",
        )
    result = await repository.set_verification(
        provider_id,
        current_user.user_id,
        payload.verified,
        payload.reason,
    )
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")
    document, _ = result
    return ProviderPrivate.model_validate(document)


@router.get(
    "/providers/{provider_id}/verification-events",
    response_model=list[ProviderVerificationEventPublic],
)
async def list_provider_verification_events(
    provider_id: str,
    _: Annotated[UserPublic, Depends(admin_user)],
    repository: Annotated[ProviderRepository, Depends(get_provider_repository)],
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[ProviderVerificationEventPublic]:
    if await repository.find_by_id(provider_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")
    return [
        ProviderVerificationEventPublic.model_validate(event)
        for event in await repository.list_verification_events(provider_id, limit)
    ]


@router.get("/service-requests", response_model=list[ServiceRequestPublic])
async def list_requests(
    _: Annotated[UserPublic, Depends(admin_user)],
    repository: Annotated[ServiceRequestRepository, Depends(get_service_request_repository)],
) -> list[ServiceRequestPublic]:
    return [
        ServiceRequestPublic.model_validate(record) for record in await repository.list_all(500)
    ]
