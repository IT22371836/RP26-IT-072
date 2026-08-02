from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import (
    get_interaction_repository,
    get_provider_repository,
    require_role,
)
from app.components.component1.service import (
    HybridRecommendationEngine,
    get_recommendation_engine,
)
from app.components.component4.provider_trust import ProviderTrustProfileService
from app.components.component4.service import (
    ArtifactsUnavailableError,
    ArtifactValidationError,
    Component4RankingEngine,
    UnknownProviderError,
    get_component4_engine,
)
from app.core.config import Settings, get_settings
from app.repositories.interactions import InteractionRepository
from app.repositories.providers import ProviderProfileExistsError, ProviderRepository
from app.schemas.auth import UserPublic
from app.schemas.common import UserRole, new_public_id, utc_now
from app.schemas.provider import ProviderCreate, ProviderPublic, ProviderTrustProfile

router = APIRouter(prefix="/providers", tags=["providers"])
provider_user = require_role(UserRole.PROVIDER)


def component1_engine_dependency(
    settings: Annotated[Settings, Depends(get_settings)],
) -> HybridRecommendationEngine:
    engine = get_recommendation_engine(settings.component1_artifact_dir)
    if not engine.ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Component 1 artifacts are not loaded",
        )
    return engine


def component4_engine_dependency(
    settings: Annotated[Settings, Depends(get_settings)],
) -> Component4RankingEngine:
    try:
        return get_component4_engine(
            settings.component4_artifact_dir,
            settings.component4_category_priors_path,
        )
    except (ArtifactsUnavailableError, ArtifactValidationError) as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error


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


@router.get("/{provider_id}/trust-profile", response_model=ProviderTrustProfile)
async def get_provider_trust_profile(
    provider_id: str,
    providers: Annotated[ProviderRepository, Depends(get_provider_repository)],
    interactions: Annotated[
        InteractionRepository,
        Depends(get_interaction_repository),
    ],
    component1: Annotated[
        HybridRecommendationEngine,
        Depends(component1_engine_dependency),
    ],
    component4: Annotated[
        Component4RankingEngine,
        Depends(component4_engine_dependency),
    ],
) -> ProviderTrustProfile:
    live_provider = await providers.find_by_id(provider_id)
    try:
        return await ProviderTrustProfileService(
            component1,
            component4,
            interactions,
        ).build(provider_id, live_provider)
    except UnknownProviderError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except OSError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Component 4 review evidence is unavailable",
        ) from error


@router.get("/{provider_id}", response_model=ProviderPublic)
async def get_provider(
    provider_id: str,
    repository: Annotated[ProviderRepository, Depends(get_provider_repository)],
) -> ProviderPublic:
    document = await repository.find_by_id(provider_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")
    return ProviderPublic.model_validate(document)
