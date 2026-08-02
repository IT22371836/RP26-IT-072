from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies import (
    get_interaction_repository,
    get_provider_repository,
    require_role,
)
from app.repositories.interactions import InteractionRepository
from app.repositories.providers import ProviderRepository
from app.schemas.auth import UserPublic
from app.schemas.common import UserRole, new_public_id, utc_now
from app.schemas.interaction import (
    InteractionCreate,
    InteractionPublic,
    InteractionType,
    RatingCreate,
)

router = APIRouter(prefix="/interactions", tags=["interactions"])
customer_user = require_role(UserRole.CUSTOMER)
provider_user = require_role(UserRole.PROVIDER)


def next_interaction(
    source: dict,
    interaction_type: InteractionType,
    rating: int | None = None,
    review_text: str | None = None,
) -> dict:
    return {
        "interaction_id": new_public_id("I"),
        "request_id": source["request_id"],
        "user_id": source["user_id"],
        "provider_id": source["provider_id"],
        "provider_name": source.get("provider_name"),
        "category": source["category"],
        "interaction_type": interaction_type.value,
        "rating": rating,
        "review_text": review_text,
        "timestamp": utc_now(),
    }


async def reject_duplicate_transition(
    repository: InteractionRepository, source: dict, interaction_type: InteractionType
) -> None:
    if await repository.has_event(
        source["user_id"], source["request_id"], source["provider_id"], interaction_type
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Booking already marked as {interaction_type.value.replace('_', ' ')}",
        )


async def reject_closed_booking(repository: InteractionRepository, source: dict) -> None:
    for interaction_type in (
        InteractionType.BOOKING_COMPLETED,
        InteractionType.BOOKING_CANCELLED,
    ):
        if await repository.has_event(
            source["user_id"], source["request_id"], source["provider_id"], interaction_type
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Booking has already been closed",
            )


async def refresh_provider_statistics(
    interactions: InteractionRepository, providers: ProviderRepository, provider_id: str
) -> None:
    await providers.update_statistics(
        provider_id, await interactions.provider_statistics(provider_id)
    )


@router.post("", response_model=InteractionPublic, status_code=status.HTTP_201_CREATED)
async def create_interaction(
    payload: InteractionCreate,
    current_user: Annotated[UserPublic, Depends(customer_user)],
    repository: Annotated[InteractionRepository, Depends(get_interaction_repository)],
) -> InteractionPublic:
    allowed_customer_events = {
        InteractionType.CLICK,
        InteractionType.SELECTED,
        InteractionType.BOOKING_REQUESTED,
    }
    if (
        payload.interaction_type not in allowed_customer_events
        or payload.rating is not None
        or payload.review_text is not None
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Ratings and reviews require a completed booking",
        )
    document = {
        **payload.model_dump(mode="json"),
        "interaction_id": new_public_id("I"),
        "user_id": current_user.user_id,
        "timestamp": utc_now(),
    }
    await repository.create(document)
    return InteractionPublic.model_validate(document)


@router.get("/me", response_model=list[InteractionPublic])
async def list_my_interactions(
    current_user: Annotated[UserPublic, Depends(customer_user)],
    repository: Annotated[InteractionRepository, Depends(get_interaction_repository)],
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[InteractionPublic]:
    records = await repository.list_for_user(current_user.user_id, limit)
    return [InteractionPublic.model_validate(record) for record in records]


@router.get("/provider/me", response_model=list[InteractionPublic])
async def list_provider_interactions(
    current_user: Annotated[UserPublic, Depends(provider_user)],
    repository: Annotated[InteractionRepository, Depends(get_interaction_repository)],
    providers: Annotated[ProviderRepository, Depends(get_provider_repository)],
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[InteractionPublic]:
    provider = await providers.find_by_user_id(current_user.user_id)
    if provider is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")
    records = await repository.list_for_provider(provider["provider_id"], limit)
    return [InteractionPublic.model_validate(record) for record in records]


@router.post("/{interaction_id}/complete", response_model=InteractionPublic)
async def complete_booking(
    interaction_id: str,
    current_user: Annotated[UserPublic, Depends(provider_user)],
    repository: Annotated[InteractionRepository, Depends(get_interaction_repository)],
    providers: Annotated[ProviderRepository, Depends(get_provider_repository)],
) -> InteractionPublic:
    provider = await providers.find_by_user_id(current_user.user_id)
    source = await repository.find_by_id(interaction_id)
    if (
        provider is None
        or source is None
        or source["provider_id"] != provider["provider_id"]
        or source["interaction_type"] != InteractionType.BOOKING_REQUESTED.value
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    await reject_closed_booking(repository, source)
    document = next_interaction(source, InteractionType.BOOKING_COMPLETED)
    await repository.create(document)
    await refresh_provider_statistics(repository, providers, source["provider_id"])
    return InteractionPublic.model_validate(document)


@router.post("/{interaction_id}/cancel", response_model=InteractionPublic)
async def cancel_booking(
    interaction_id: str,
    current_user: Annotated[UserPublic, Depends(provider_user)],
    repository: Annotated[InteractionRepository, Depends(get_interaction_repository)],
    providers: Annotated[ProviderRepository, Depends(get_provider_repository)],
) -> InteractionPublic:
    provider = await providers.find_by_user_id(current_user.user_id)
    source = await repository.find_by_id(interaction_id)
    if (
        provider is None
        or source is None
        or source["provider_id"] != provider["provider_id"]
        or source["interaction_type"] != InteractionType.BOOKING_REQUESTED.value
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    await reject_closed_booking(repository, source)
    document = next_interaction(source, InteractionType.BOOKING_CANCELLED)
    await repository.create(document)
    await refresh_provider_statistics(repository, providers, source["provider_id"])
    return InteractionPublic.model_validate(document)


@router.post("/{interaction_id}/rate", response_model=InteractionPublic)
async def rate_completed_booking(
    interaction_id: str,
    payload: RatingCreate,
    current_user: Annotated[UserPublic, Depends(customer_user)],
    repository: Annotated[InteractionRepository, Depends(get_interaction_repository)],
    providers: Annotated[ProviderRepository, Depends(get_provider_repository)],
) -> InteractionPublic:
    source = await repository.find_by_id(interaction_id)
    if (
        source is None
        or source["user_id"] != current_user.user_id
        or source["interaction_type"] != InteractionType.BOOKING_COMPLETED.value
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Completed booking not found"
        )
    await reject_duplicate_transition(repository, source, InteractionType.RATED)
    document = next_interaction(
        source,
        InteractionType.RATED,
        payload.rating,
        payload.review_text,
    )
    await repository.create(document)
    await refresh_provider_statistics(repository, providers, source["provider_id"])
    return InteractionPublic.model_validate(document)
