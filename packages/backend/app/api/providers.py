from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_provider_repository, require_role
from app.repositories.providers import ProviderProfileExistsError, ProviderRepository
from app.schemas.auth import UserPublic
from app.schemas.common import UserRole, new_public_id, utc_now
from app.schemas.provider import ProviderCreate, ProviderPublic

router = APIRouter(prefix="/providers", tags=["providers"])
provider_user = require_role(UserRole.PROVIDER)


@router.post("/me", response_model=ProviderPublic, status_code=status.HTTP_201_CREATED)
async def create_my_provider_profile(
    payload: ProviderCreate,
    current_user: Annotated[UserPublic, Depends(provider_user)],
    repository: Annotated[ProviderRepository, Depends(get_provider_repository)],
) -> ProviderPublic:
    now = utc_now()
    document = {
        **payload.model_dump(),
        "provider_id": new_public_id("P"),
        "user_id": current_user.user_id,
        "rating": 0.0,
        "review_count": 0,
        "booking_success_rate": 0.0,
        "interaction_count": 0,
        "created_at": now,
        "updated_at": now,
    }
    try:
        await repository.create(document)
    except ProviderProfileExistsError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Provider profile already exists",
        ) from error
    return ProviderPublic.model_validate(document)


@router.get("/me", response_model=ProviderPublic)
async def get_my_provider_profile(
    current_user: Annotated[UserPublic, Depends(provider_user)],
    repository: Annotated[ProviderRepository, Depends(get_provider_repository)],
) -> ProviderPublic:
    document = await repository.find_by_user_id(current_user.user_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")
    return ProviderPublic.model_validate(document)


@router.get("/{provider_id}", response_model=ProviderPublic)
async def get_provider(
    provider_id: str,
    repository: Annotated[ProviderRepository, Depends(get_provider_repository)],
) -> ProviderPublic:
    document = await repository.find_by_id(provider_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")
    return ProviderPublic.model_validate(document)
