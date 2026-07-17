from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import require_role
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
from app.schemas.auth import UserPublic
from app.schemas.common import UserRole

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
) -> RecommendationResponse:
    try:
        results = engine.recommend(
            query=payload.query,
            user_id=current_user.user_id,
            top_k=payload.top_k,
            category=payload.category,
            district=payload.district,
            city=payload.city,
            min_rating=payload.min_rating,
        )
    except (ArtifactsUnavailableError, ArtifactValidationError) as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error
    return RecommendationResponse(
        component_version=engine.manifest["component_version"],
        model_version=engine.manifest["model_version"],
        query=payload.query,
        user_id=current_user.user_id,
        results=results,
    )
