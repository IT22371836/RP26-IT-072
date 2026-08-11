from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, time
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status

from app.api.dependencies import (
    get_firebase_rtdb_client,
    get_pipeline_repository,
    get_service_request_repository,
    get_user_repository,
    require_firebase_role,
)
from app.core.config import Settings, get_settings
from app.integrations.firebase_component2 import FirebaseComponent2Error, FirebaseRtdbClient
from app.pipeline.schemas import (
    PipelineRunCreate,
    PipelineRunResponse,
    PipelineSelectionRequest,
    PipelineSelectionResponse,
    PipelineStartResponse,
    PipelineStatus,
)
from app.repositories.pipeline import PipelineRepository
from app.repositories.service_requests import ServiceRequestRepository
from app.repositories.users import UserRepository
from app.schemas.auth import UserPublic
from app.schemas.common import UserRole, new_public_id, utc_now

router = APIRouter(prefix="/pipeline/runs", tags=["pipeline"])
customer_user = require_firebase_role(UserRole.CUSTOMER)
customer_or_admin = require_firebase_role(UserRole.CUSTOMER, UserRole.ADMIN)


def _response(document: dict[str, Any]) -> PipelineRunResponse:
    return PipelineRunResponse.model_validate(document)


def _fingerprint(payload: PipelineRunCreate) -> str:
    canonical = json.dumps(
        payload.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


@router.get("/worker-health")
async def pipeline_worker_health(
    current_user: Annotated[UserPublic, Depends(customer_or_admin)],
    repository: Annotated[PipelineRepository, Depends(get_pipeline_repository)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    worker = await repository.get_worker(settings.pipeline_worker_id)
    heartbeat = worker.get("heartbeat_at") if worker else None
    age_seconds = (utc_now() - heartbeat).total_seconds() if heartbeat else None
    return {
        "ready": age_seconds is not None and age_seconds <= max(
            10, settings.pipeline_poll_interval_seconds * 5
        ),
        "worker_id": settings.pipeline_worker_id,
        "active_run_id": worker.get("active_run_id") if worker else None,
        "heartbeat_at": heartbeat,
        "age_seconds": age_seconds,
    }


@router.post("", response_model=PipelineStartResponse, status_code=status.HTTP_202_ACCEPTED)
async def start_pipeline(
    payload: PipelineRunCreate,
    request: Request,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=200)],
    current_user: Annotated[UserPublic, Depends(customer_user)],
    repository: Annotated[PipelineRepository, Depends(get_pipeline_repository)],
    users: Annotated[UserRepository, Depends(get_user_repository)],
    service_requests: Annotated[
        ServiceRequestRepository, Depends(get_service_request_repository)
    ],
) -> PipelineStartResponse:
    user = await users.find_by_id(current_user.user_id)
    if not (user or {}).get("legacy", {}).get("firebase_uid"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Link this customer account to Firebase before starting a pipeline run",
        )
    now = utc_now()
    run_id = new_public_id("PIPE")
    request_id = new_public_id("R")
    document = {
        "run_id": run_id,
        "request_id": request_id,
        "user_id": current_user.user_id,
        "idempotency_key": idempotency_key.strip(),
        "request_fingerprint": _fingerprint(payload),
        "request": payload.model_dump(mode="json"),
        "status": PipelineStatus.INITIALIZING.value,
        "attempt_count": 0,
        "retry_history": [],
        "selected_provider_id": None,
        "booking_interaction_id": None,
        "selected_at": None,
        "created_at": now,
        "updated_at": now,
    }
    stored, created = await repository.create_or_get(document)
    if not created:
        if stored.get("request_fingerprint") != document["request_fingerprint"]:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Idempotency-Key was already used with a different request",
            )
    else:
        try:
            await service_requests.create(
                {
                    "request_id": request_id,
                    "pipeline_run_id": run_id,
                    "user_id": current_user.user_id,
                    "description": payload.request_text,
                    "category": payload.category,
                    "district": payload.district,
                    "city": payload.city,
                    "urgency": payload.urgency.value,
                    "service_date": payload.service_date.isoformat(),
                    "service_time": payload.service_time.model_dump(),
                    "location_type": payload.location_type,
                    "status": "pipeline_created",
                    "created_at": now,
                    "updated_at": now,
                }
            )
            stored = await repository.mark_created(run_id)
        except Exception:
            await repository.collection.delete_one(
                {"run_id": run_id, "status": PipelineStatus.INITIALIZING.value}
            )
            raise
    return PipelineStartResponse(
        run_id=stored["run_id"],
        request_id=stored["request_id"],
        status=PipelineStatus(stored["status"]),
        status_url=str(request.url_for("get_pipeline_run", run_id=stored["run_id"])),
        created_at=stored["created_at"],
    )


@router.get("", response_model=list[PipelineRunResponse])
async def list_pipeline_runs(
    current_user: Annotated[UserPublic, Depends(customer_or_admin)],
    repository: Annotated[PipelineRepository, Depends(get_pipeline_repository)],
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
    user_id: str | None = None,
    run_status: Annotated[str | None, Query(alias="status")] = None,
    created_from: date | None = None,
    created_to: date | None = None,
) -> list[PipelineRunResponse]:
    if current_user.role == UserRole.CUSTOMER:
        records = await repository.list_for_user(current_user.user_id, limit, offset)
    else:
        filters: dict[str, Any] = {}
        if user_id:
            filters["user_id"] = user_id
        if run_status:
            try:
                filters["status"] = PipelineStatus(run_status).value
            except ValueError as error:
                raise HTTPException(status_code=422, detail="Unknown pipeline status") from error
        if created_from or created_to:
            created_filter: dict[str, datetime] = {}
            if created_from:
                created_filter["$gte"] = datetime.combine(
                    created_from, time.min, tzinfo=utc_now().tzinfo
                )
            if created_to:
                created_filter["$lte"] = datetime.combine(
                    created_to, time.max, tzinfo=utc_now().tzinfo
                )
            filters["created_at"] = created_filter
        records = await repository.list_all(limit, offset, filters)
    return [_response(record) for record in records]


@router.get("/{run_id}", response_model=PipelineRunResponse, name="get_pipeline_run")
async def get_pipeline_run(
    run_id: str,
    current_user: Annotated[UserPublic, Depends(customer_or_admin)],
    repository: Annotated[PipelineRepository, Depends(get_pipeline_repository)],
) -> PipelineRunResponse:
    document = await repository.find_by_id(run_id)
    if document is None or (
        current_user.role != UserRole.ADMIN and document["user_id"] != current_user.user_id
    ):
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    return _response(document)


@router.post("/{run_id}/retry", response_model=PipelineRunResponse)
async def retry_pipeline_run(
    run_id: str,
    current_user: Annotated[UserPublic, Depends(customer_user)],
    repository: Annotated[PipelineRepository, Depends(get_pipeline_repository)],
) -> PipelineRunResponse:
    document = await repository.retry(run_id, current_user.user_id)
    if document is None:
        raise HTTPException(
            status_code=409,
            detail="Only an owned, retryable failed run can be retried",
        )
    await repository.collection.update_one(
        {"run_id": run_id},
        {
            "$push": {
                "retry_history": {
                    "requested_at": utc_now(),
                    "requested_by": current_user.user_id,
                }
            }
        },
    )
    return _response(document)


@router.post("/{run_id}/selection", response_model=PipelineSelectionResponse)
async def select_pipeline_provider(
    run_id: str,
    payload: PipelineSelectionRequest,
    current_user: Annotated[UserPublic, Depends(customer_user)],
    repository: Annotated[PipelineRepository, Depends(get_pipeline_repository)],
    users: Annotated[UserRepository, Depends(get_user_repository)],
    firebase: Annotated[FirebaseRtdbClient, Depends(get_firebase_rtdb_client)],
) -> PipelineSelectionResponse:
    existing = await repository.find_by_id(run_id)
    provider = next(
        (
            item
            for item in (existing or {}).get("component4", {}).get("providers", [])
            if item["provider_id"] == payload.provider_id
        ),
        None,
    )
    if (
        existing is None
        or existing.get("user_id") != current_user.user_id
        or existing.get("status") != PipelineStatus.COMPLETED.value
        or provider is None
    ):
        raise HTTPException(status_code=409, detail="Provider is not selectable for this run")
    booking_id = new_public_id("I")
    now = utc_now()
    user = await users.find_by_id(current_user.user_id)
    firebase_uid = (user or {}).get("legacy", {}).get("firebase_uid")
    if not firebase_uid:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Customer has no Firebase booking-history identity",
        )
    base = {
        "request_id": existing["request_id"],
        "pipeline_run_id": run_id,
        "user_id": current_user.user_id,
        "provider_id": payload.provider_id,
        "provider_name": provider.get("provider_name"),
        "category": provider["category"],
        "rating": None,
        "review_text": None,
        "timestamp": now,
    }
    firebase_booking = {
        "booking_id": booking_id,
        "request_id": existing["request_id"],
        "pipeline_run_id": run_id,
        "customer_uid": firebase_uid,
        "provider_id": payload.provider_id,
        "provider_name": provider.get("provider_name"),
        "category": provider["category"],
        "status": "booking_requested",
        "requested_at": now.isoformat(),
        "updated_at": now.isoformat(),
        "completed_at": None,
        "cancelled_at": None,
        "rating": None,
        "review_text": None,
        "rated_at": None,
        "source": "pipeline",
    }
    try:
        firebase_created = await firebase.create_customer_booking(
            firebase_uid, booking_id, firebase_booking
        )
    except FirebaseComponent2Error as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Firebase booking history is unavailable",
        ) from error
    try:
        run = await repository.create_selection_with_interactions(
            run_id,
            current_user.user_id,
            payload.provider_id,
            booking_id,
            [
                {
                    **base,
                    "interaction_id": new_public_id("I"),
                    "interaction_type": "selected",
                },
                {
                    **base,
                    "interaction_id": booking_id,
                    "interaction_type": "booking_requested",
                },
            ],
        )
    except Exception as error:
        if firebase_created:
            try:
                await firebase.delete_customer_booking_if_matching(
                    firebase_uid, booking_id, run_id
                )
            except Exception:
                pass
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Booking persistence is temporarily unavailable",
        ) from error
    if run is None:
        if firebase_created:
            await firebase.delete_customer_booking_if_matching(
                firebase_uid, booking_id, run_id
            )
        raise HTTPException(
            status_code=409,
            detail="Provider must be in this run's final Top-5 and no prior selection may exist",
        )
    return PipelineSelectionResponse(
        run_id=run_id,
        request_id=existing["request_id"],
        provider_id=payload.provider_id,
        booking_interaction_id=booking_id,
    )
