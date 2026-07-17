from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import (
    get_interaction_repository,
    get_provider_repository,
    require_role,
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
from app.repositories.interactions import InteractionRepository
from app.repositories.providers import ProviderRepository
from app.schemas.auth import UserPublic
from app.schemas.common import UserRole, new_public_id, utc_now

router = APIRouter(prefix="/component1", tags=["component 1"])
customer_user = require_role(UserRole.CUSTOMER)


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
    provider_repository: Annotated[ProviderRepository, Depends(get_provider_repository)],
    interaction_repository: Annotated[InteractionRepository, Depends(get_interaction_repository)],
) -> RecommendationResponse:
    try:
        live_providers = await provider_repository.list_all()
        live_preferences = await interaction_repository.preferred_provider_ids(current_user.user_id)
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
        )
    except (ArtifactsUnavailableError, ArtifactValidationError) as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error
    now = utc_now()
    await interaction_repository.create_many(
        [
            {
                "interaction_id": new_public_id("I"),
                "request_id": payload.request_id,
                "user_id": current_user.user_id,
                "provider_id": result.provider_id,
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
