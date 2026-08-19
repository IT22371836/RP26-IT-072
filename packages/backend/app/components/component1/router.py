from time import perf_counter
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import (
    get_component1_repository,
    get_firebase_rtdb_client,
    get_interaction_repository,
    get_provider_repository,
    get_service_request_repository,
    get_user_repository,
    require_firebase_role,
)
from app.components.component1.schemas import (
    ComponentStatusResponse,
    RecommendationRequest,
    RecommendationResponse,
)
from app.components.component1.service import (
    ArtifactsUnavailableError,
    ArtifactValidationError,
    HybridRecommendationEngine,
    get_recommendation_engine,
)
from app.core.config import Settings, get_settings
from app.integrations.firebase_component2 import (
    FirebaseComponent2Error,
    FirebaseRtdbClient,
    booking_history_preference_ids,
    merge_verified_provider_candidates,
)
from app.repositories.component1 import Component1Repository
from app.repositories.interactions import InteractionRepository
from app.repositories.providers import ProviderRepository
from app.repositories.service_requests import ServiceRequestRepository
from app.repositories.users import UserRepository
from app.schemas.auth import UserPublic
from app.schemas.common import UserRole, new_public_id, utc_now
from app.services.provider_eligibility import eligible_provider_pool

router = APIRouter(prefix="/component1", tags=["component 1"])
customer_user = require_firebase_role(UserRole.CUSTOMER)


def engine_dependency(
    settings: Annotated[Settings, Depends(get_settings)],
) -> HybridRecommendationEngine:
    return get_recommendation_engine(settings.component1_artifact_dir)


@router.get("/status", response_model=ComponentStatusResponse)
async def component_status(
    engine: Annotated[HybridRecommendationEngine, Depends(engine_dependency)],
) -> ComponentStatusResponse:
    return ComponentStatusResponse.model_validate(engine.status())


@router.post("/recommend", response_model=RecommendationResponse)
async def recommend(
    payload: RecommendationRequest,
    current_user: Annotated[UserPublic, Depends(customer_user)],
    engine: Annotated[HybridRecommendationEngine, Depends(engine_dependency)],
    settings: Annotated[Settings, Depends(get_settings)],
    provider_repository: Annotated[ProviderRepository, Depends(get_provider_repository)],
    interaction_repository: Annotated[InteractionRepository, Depends(get_interaction_repository)],
    user_repository: Annotated[UserRepository, Depends(get_user_repository)],
    firebase: Annotated[FirebaseRtdbClient, Depends(get_firebase_rtdb_client)],
    service_request_repository: Annotated[
        ServiceRequestRepository,
        Depends(get_service_request_repository),
    ],
    component1_repository: Annotated[
        Component1Repository,
        Depends(get_component1_repository),
    ],
) -> RecommendationResponse:
    request = await service_request_repository.find_by_id(payload.request_id)
    if request is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service request not found",
        )
    if request.get("user_id") != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The service request belongs to another customer",
        )
    try:
        started_at = utc_now()
        started_timer = perf_counter()
        provider_profiles = await provider_repository.list_pipeline_eligible(
            limit=20_000,
            cache_seconds=settings.pipeline_provider_cache_seconds,
        )
        artifact_provider_ids = {
            str(provider["provider_id"]) for provider in engine.providers
        }
        pool = eligible_provider_pool(provider_profiles, artifact_provider_ids)
        live_providers = merge_verified_provider_candidates(
            artifact_provider_ids,
            [],
            pool.eligible_profiles,
        )
        user_document = await user_repository.find_by_id(current_user.user_id)
        firebase_uid = (user_document or {}).get("legacy", {}).get("firebase_uid")
        if not firebase_uid:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Customer has no Firebase booking-history identity",
            )
        try:
            booking_history = await firebase.get_customer_booking_history(firebase_uid)
        except FirebaseComponent2Error as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Firebase booking history is unavailable",
            ) from error
        click_preferences = await interaction_repository.click_preference_provider_ids(
            current_user.user_id
        )
        live_preferences = [
            *booking_history_preference_ids(booking_history),
            *click_preferences,
        ]
        results = engine.recommend(
            query=payload.query,
            user_id=current_user.user_id,
            top_k=payload.top_k,
            category=payload.category,
            district=payload.district,
            city=payload.city,
            min_rating=payload.min_rating,
            additional_providers=live_providers,
            additional_preferences=live_preferences,
            allowed_provider_ids=pool.allowed_provider_ids,
        )
        processing_time_ms = round((perf_counter() - started_timer) * 1000, 3)
    except (ArtifactsUnavailableError, ArtifactValidationError) as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error
    now = utc_now()
    run_id = new_public_id("C1RUN")
    score_documents = [
        {
            "run_id": run_id,
            "request_id": payload.request_id,
            "user_id": current_user.user_id,
            "provider_id": result.provider_id,
            "provider_name": result.provider_name,
            "category": result.category,
            "rank": rank,
            "cf_score": result.cf_score,
            "tfidf_score": result.tfidf_score,
            "bert_score": result.bert_score,
            "hybrid_score": result.hybrid_score,
            "component_version": engine.manifest["component_version"],
            "model_version": engine.manifest["model_version"],
            "created_at": now,
        }
        for rank, result in enumerate(results, start=1)
    ]
    await component1_repository.persist_completed(
        {
            "run_id": run_id,
            "request_id": payload.request_id,
            "user_id": current_user.user_id,
            "query": payload.query,
            "filters": {
                "category": payload.category,
                "district": payload.district,
                "city": payload.city,
                "min_rating": payload.min_rating,
            },
            "requested_top_k": payload.top_k,
            "output_count": len(results),
            "component_version": engine.manifest["component_version"],
            "model_version": engine.manifest["model_version"],
            "processing_time_ms": processing_time_ms,
            "started_at": started_at,
        },
        score_documents,
    )
    await interaction_repository.create_many(
        [
            {
                "interaction_id": new_public_id("I"),
                "request_id": payload.request_id,
                "user_id": current_user.user_id,
                "provider_id": result.provider_id,
                "provider_name": result.provider_name,
                "category": result.category,
                "interaction_type": "impression",
                "rating": None,
                "timestamp": now,
            }
            for result in results
        ]
    )
    return RecommendationResponse(
        component_version=engine.manifest["component_version"],
        model_version=engine.manifest["model_version"],
        request_id=payload.request_id,
        query=payload.query,
        user_id=current_user.user_id,
        results=results,
    )
