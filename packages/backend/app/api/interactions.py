from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies import (
    get_firebase_rtdb_client,
    get_interaction_repository,
    get_provider_repository,
    get_user_repository,
    require_firebase_role,
)
from app.integrations.firebase_component2 import (
    FirebaseComponent2Error,
    FirebaseRequestConflictError,
    FirebaseRtdbClient,
)
from app.repositories.interactions import InteractionRepository
from app.repositories.providers import ProviderRepository
from app.repositories.users import UserRepository
from app.schemas.auth import UserPublic
from app.schemas.common import UserRole, new_public_id, utc_now
from app.schemas.interaction import (
    InteractionCreate,
    InteractionPublic,
    InteractionType,
    RatingCreate,
)

router = APIRouter(prefix="/interactions", tags=["interactions"])
customer_user = require_firebase_role(UserRole.CUSTOMER)
provider_user = require_firebase_role(UserRole.PROVIDER)


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
        "booking_interaction_id": source.get("booking_interaction_id")
        or source.get("interaction_id"),
        "pipeline_run_id": source.get("pipeline_run_id"),
        "request_details": source.get("request_details"),
    }


async def firebase_uid_for_user(users: UserRepository, user_id: str) -> str:
    user = await users.find_by_id(user_id)
    firebase_uid = (user or {}).get("legacy", {}).get("firebase_uid")
    if not firebase_uid:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Customer has no Firebase booking-history identity",
        )
    return str(firebase_uid)


async def ensure_firebase_booking(
    firebase: FirebaseRtdbClient,
    firebase_uid: str,
    booking_id: str,
    source: dict,
) -> None:
    requested_at = source.get("timestamp") or utc_now()
    requested_text = (
        requested_at.isoformat() if hasattr(requested_at, "isoformat") else str(requested_at)
    )
    await firebase.create_customer_booking(
        firebase_uid,
        booking_id,
        {
            "booking_id": booking_id,
            "request_id": source["request_id"],
            "pipeline_run_id": source.get("pipeline_run_id"),
            "customer_uid": firebase_uid,
            "provider_id": source["provider_id"],
            "provider_name": source.get("provider_name"),
            "category": source["category"],
            "status": "booking_requested",
            "requested_at": requested_text,
            "updated_at": requested_text,
            "accepted_at": None,
            "rejected_at": None,
            "completed_at": None,
            "cancelled_at": None,
            "rating": None,
            "review_text": None,
            "rated_at": None,
            "source": "interaction_api",
        },
    )


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
        InteractionType.BOOKING_REJECTED,
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


async def reject_responded_booking(repository: InteractionRepository, source: dict) -> None:
    for interaction_type in (
        InteractionType.BOOKING_ACCEPTED,
        InteractionType.BOOKING_REJECTED,
    ):
        if await repository.has_event(
            source["user_id"], source["request_id"], source["provider_id"], interaction_type
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Booking has already been accepted or rejected",
            )


async def require_accepted_booking(repository: InteractionRepository, source: dict) -> None:
    if not await repository.has_event(
        source["user_id"],
        source["request_id"],
        source["provider_id"],
        InteractionType.BOOKING_ACCEPTED,
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Accept the booking before completing or cancelling it",
        )


async def transition_firebase_booking(
    firebase: FirebaseRtdbClient,
    firebase_uid: str,
    booking_id: str,
    expected_statuses: set[str],
    updates: dict,
) -> None:
    try:
        await firebase.transition_customer_booking(
            firebase_uid, booking_id, expected_statuses, updates
        )
    except FirebaseRequestConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Booking status changed; refresh and try again",
        ) from error
    except FirebaseComponent2Error as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Firebase booking history is unavailable",
        ) from error


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
    users: Annotated[UserRepository, Depends(get_user_repository)],
    firebase: Annotated[FirebaseRtdbClient, Depends(get_firebase_rtdb_client)],
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
    if payload.interaction_type == InteractionType.BOOKING_REQUESTED:
        firebase_uid = await firebase_uid_for_user(users, current_user.user_id)
        try:
            await ensure_firebase_booking(
                firebase, firebase_uid, document["interaction_id"], document
            )
        except FirebaseComponent2Error as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Firebase booking history is unavailable",
            ) from error
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


@router.post("/{interaction_id}/accept", response_model=InteractionPublic)
async def accept_booking(
    interaction_id: str,
    current_user: Annotated[UserPublic, Depends(provider_user)],
    repository: Annotated[InteractionRepository, Depends(get_interaction_repository)],
    providers: Annotated[ProviderRepository, Depends(get_provider_repository)],
    users: Annotated[UserRepository, Depends(get_user_repository)],
    firebase: Annotated[FirebaseRtdbClient, Depends(get_firebase_rtdb_client)],
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
    await reject_responded_booking(repository, source)
    firebase_uid = await firebase_uid_for_user(users, source["user_id"])
    try:
        await ensure_firebase_booking(firebase, firebase_uid, source["interaction_id"], source)
    except FirebaseComponent2Error as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Firebase booking history is unavailable",
        ) from error
    document = next_interaction(source, InteractionType.BOOKING_ACCEPTED)
    responded_at = document["timestamp"].isoformat()
    await transition_firebase_booking(
        firebase,
        firebase_uid,
        source["interaction_id"],
        {InteractionType.BOOKING_REQUESTED.value},
        {
            "status": InteractionType.BOOKING_ACCEPTED.value,
            "accepted_at": responded_at,
            "rejected_at": None,
            "updated_at": responded_at,
        },
    )
    await repository.create(document)
    return InteractionPublic.model_validate(document)


@router.post("/{interaction_id}/reject", response_model=InteractionPublic)
async def reject_booking(
    interaction_id: str,
    current_user: Annotated[UserPublic, Depends(provider_user)],
    repository: Annotated[InteractionRepository, Depends(get_interaction_repository)],
    providers: Annotated[ProviderRepository, Depends(get_provider_repository)],
    users: Annotated[UserRepository, Depends(get_user_repository)],
    firebase: Annotated[FirebaseRtdbClient, Depends(get_firebase_rtdb_client)],
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
    await reject_responded_booking(repository, source)
    firebase_uid = await firebase_uid_for_user(users, source["user_id"])
    try:
        await ensure_firebase_booking(firebase, firebase_uid, source["interaction_id"], source)
    except FirebaseComponent2Error as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Firebase booking history is unavailable",
        ) from error
    document = next_interaction(source, InteractionType.BOOKING_REJECTED)
    responded_at = document["timestamp"].isoformat()
    await transition_firebase_booking(
        firebase,
        firebase_uid,
        source["interaction_id"],
        {InteractionType.BOOKING_REQUESTED.value},
        {
            "status": InteractionType.BOOKING_REJECTED.value,
            "accepted_at": None,
            "rejected_at": responded_at,
            "updated_at": responded_at,
        },
    )
    await repository.create(document)
    return InteractionPublic.model_validate(document)


@router.post("/{interaction_id}/complete", response_model=InteractionPublic)
async def complete_booking(
    interaction_id: str,
    current_user: Annotated[UserPublic, Depends(provider_user)],
    repository: Annotated[InteractionRepository, Depends(get_interaction_repository)],
    providers: Annotated[ProviderRepository, Depends(get_provider_repository)],
    users: Annotated[UserRepository, Depends(get_user_repository)],
    firebase: Annotated[FirebaseRtdbClient, Depends(get_firebase_rtdb_client)],
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
    await require_accepted_booking(repository, source)
    firebase_uid = await firebase_uid_for_user(users, source["user_id"])
    try:
        await ensure_firebase_booking(firebase, firebase_uid, source["interaction_id"], source)
    except FirebaseComponent2Error as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Firebase booking history is unavailable",
        ) from error
    now = utc_now()
    await transition_firebase_booking(
        firebase,
        firebase_uid,
        source["interaction_id"],
        {InteractionType.BOOKING_ACCEPTED.value},
        {
            "status": InteractionType.BOOKING_COMPLETED.value,
            "completed_at": now.isoformat(),
            "updated_at": now.isoformat(),
        },
    )
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
    users: Annotated[UserRepository, Depends(get_user_repository)],
    firebase: Annotated[FirebaseRtdbClient, Depends(get_firebase_rtdb_client)],
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
    await require_accepted_booking(repository, source)
    firebase_uid = await firebase_uid_for_user(users, source["user_id"])
    try:
        await ensure_firebase_booking(firebase, firebase_uid, source["interaction_id"], source)
    except FirebaseComponent2Error as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Firebase booking history is unavailable",
        ) from error
    now = utc_now()
    await transition_firebase_booking(
        firebase,
        firebase_uid,
        source["interaction_id"],
        {InteractionType.BOOKING_ACCEPTED.value},
        {
            "status": InteractionType.BOOKING_CANCELLED.value,
            "cancelled_at": now.isoformat(),
            "updated_at": now.isoformat(),
        },
    )
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
    users: Annotated[UserRepository, Depends(get_user_repository)],
    firebase: Annotated[FirebaseRtdbClient, Depends(get_firebase_rtdb_client)],
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
    booking_id = source.get("booking_interaction_id")
    booking_source = None
    if not booking_id:
        booking_source = await repository.find_booking_requested(
            source["user_id"], source["request_id"], source["provider_id"]
        )
        booking_id = (booking_source or {}).get("interaction_id")
    if not booking_id:
        raise HTTPException(status_code=409, detail="Original booking request was not found")
    firebase_uid = await firebase_uid_for_user(users, source["user_id"])
    document = next_interaction(
        source,
        InteractionType.RATED,
        payload.rating,
        payload.review_text,
    )
    rated_at = document["timestamp"].isoformat()
    try:
        await ensure_firebase_booking(
            firebase, firebase_uid, str(booking_id), booking_source or source
        )
        await firebase.update_customer_booking(
            firebase_uid,
            str(booking_id),
            {
                "status": "booking_completed",
                "rating": payload.rating,
                "review_text": payload.review_text,
                "rated_at": rated_at,
                "updated_at": rated_at,
            },
        )
        await firebase.create_provider_review(
            source["provider_id"],
            str(booking_id),
            {
                "review_id": str(booking_id),
                "booking_id": str(booking_id),
                "request_id": source["request_id"],
                "customer_uid": firebase_uid,
                "provider_id": source["provider_id"],
                "provider_name": source.get("provider_name"),
                "category": source["category"],
                "rating": payload.rating,
                "review_text": payload.review_text,
                "reviewed_at": rated_at,
                "verified_booking": True,
                "source": "platform_booking",
            },
        )
        await firebase.refresh_provider_review_statistics(source["provider_id"])
    except FirebaseComponent2Error as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Firebase customer/provider review storage is unavailable",
        ) from error
    await repository.create(document)
    await refresh_provider_statistics(repository, providers, source["provider_id"])
    return InteractionPublic.model_validate(document)
