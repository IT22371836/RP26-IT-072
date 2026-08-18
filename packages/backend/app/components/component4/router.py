import time
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import (
    get_component4_repository,
    get_provider_repository,
    get_service_request_repository,
    require_firebase_role,
)
from app.components.component4.schemas import (
    Component4FinalReadinessResponse,
    Component4HandoffReadinessResponse,
    Component4HealthResponse,
    Component4IntegrationReadinessResponse,
    Component4ModelsResponse,
    Component4RankRequest,
    Component4RankResponse,
    Component4ReleaseReadinessResponse,
    Component4RuntimeMetricsResponse,
    Component4WeightResponse,
)
from app.components.component4.service import (
    ArtifactsUnavailableError,
    ArtifactValidationError,
    Component4RankingEngine,
    Component4RankingOrchestrator,
    UnknownProviderError,
    get_component4_engine,
)
from app.components.component4.telemetry import component4_runtime_telemetry
from app.core.config import Settings, get_settings
from app.core.firebase_database import FirebaseDatabase
from app.repositories.component4 import Component4Repository
from app.repositories.providers import ProviderRepository
from app.repositories.service_requests import ServiceRequestRepository
from app.schemas.auth import UserPublic
from app.schemas.common import UserRole

router = APIRouter(prefix="/component4", tags=["component 4"])
customer_user = require_firebase_role(UserRole.CUSTOMER)
admin_user = require_firebase_role(UserRole.ADMIN)


def engine_dependency(
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


@router.post("/rank", response_model=Component4RankResponse)
async def rank_candidates(
    payload: Component4RankRequest,
    current_user: Annotated[UserPublic, Depends(customer_user)],
    settings: Annotated[Settings, Depends(get_settings)],
    engine: Annotated[Component4RankingEngine, Depends(engine_dependency)],
    component4_repository: Annotated[
        Component4Repository,
        Depends(get_component4_repository),
    ],
    provider_repository: Annotated[
        ProviderRepository,
        Depends(get_provider_repository),
    ],
    service_request_repository: Annotated[
        ServiceRequestRepository,
        Depends(get_service_request_repository),
    ],
) -> Component4RankResponse:
    started = time.perf_counter()
    response_status = status.HTTP_500_INTERNAL_SERVER_ERROR
    cached: bool | None = None
    try:
        response = await _execute_ranking(
            payload=payload,
            current_user=current_user,
            settings=settings,
            engine=engine,
            component4_repository=component4_repository,
            provider_repository=provider_repository,
            service_request_repository=service_request_repository,
        )
        response_status = status.HTTP_200_OK
        cached = response.cached
        return response
    except HTTPException as error:
        response_status = error.status_code
        raise
    finally:
        component4_runtime_telemetry.record(
            status_code=response_status,
            duration_ms=(time.perf_counter() - started) * 1000,
            cached=cached,
        )


async def _execute_ranking(
    *,
    payload: Component4RankRequest,
    current_user: UserPublic,
    settings: Settings,
    engine: Component4RankingEngine,
    component4_repository: Component4Repository,
    provider_repository: ProviderRepository,
    service_request_repository: ServiceRequestRepository,
) -> Component4RankResponse:
    if payload.user_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The Component 4 handoff user does not match the authenticated customer",
        )
    if settings.app_env.lower() == "production" and payload.source == "development_fixture":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The Component 2 development fixture is forbidden in production",
        )
    try:
        request = await service_request_repository.find_by_id(payload.request_id)
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Component 4 could not access the shared database",
        ) from error
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
        live_providers = await provider_repository.list_by_ids(payload.provider_ids)
        return await Component4RankingOrchestrator(
            engine,
            component4_repository,
        ).rank(
            payload,
            user_id=current_user.user_id,
            live_providers=live_providers,
        )
    except UnknownProviderError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except (ArtifactsUnavailableError, ArtifactValidationError) as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Component 4 ranking persistence is unavailable",
        ) from error


@router.get("/runs/{run_id}", response_model=Component4RankResponse)
async def get_run(
    run_id: str,
    current_user: Annotated[UserPublic, Depends(customer_user)],
    repository: Annotated[
        Component4Repository,
        Depends(get_component4_repository),
    ],
) -> Component4RankResponse:
    try:
        response = await repository.find_completed_response(run_id, current_user.user_id)
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Component 4 run storage is unavailable",
        ) from error
    if response is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Component 4 run not found",
        )
    return Component4RankResponse.model_validate({**response, "cached": True})


@router.get("/models", response_model=Component4ModelsResponse)
async def active_models(
    engine: Annotated[Component4RankingEngine, Depends(engine_dependency)],
) -> Component4ModelsResponse:
    return Component4ModelsResponse.model_validate(engine.status())


@router.get(
    "/integration-readiness",
    response_model=Component4IntegrationReadinessResponse,
)
async def integration_readiness(
    engine: Annotated[Component4RankingEngine, Depends(engine_dependency)],
) -> Component4IntegrationReadinessResponse:
    return Component4IntegrationReadinessResponse.model_validate(engine.integration_readiness())


@router.get(
    "/release-readiness",
    response_model=Component4ReleaseReadinessResponse,
)
async def release_readiness(
    engine: Annotated[Component4RankingEngine, Depends(engine_dependency)],
) -> Component4ReleaseReadinessResponse:
    return Component4ReleaseReadinessResponse.model_validate(engine.release_readiness())


@router.get(
    "/handoff-readiness",
    response_model=Component4HandoffReadinessResponse,
)
async def handoff_readiness(
    engine: Annotated[Component4RankingEngine, Depends(engine_dependency)],
) -> Component4HandoffReadinessResponse:
    return Component4HandoffReadinessResponse.model_validate(engine.handoff_readiness())


@router.get(
    "/final-readiness",
    response_model=Component4FinalReadinessResponse,
)
async def final_readiness(
    engine: Annotated[Component4RankingEngine, Depends(engine_dependency)],
) -> Component4FinalReadinessResponse:
    return Component4FinalReadinessResponse.model_validate(engine.final_readiness())


@router.get(
    "/runtime-metrics",
    response_model=Component4RuntimeMetricsResponse,
)
async def runtime_metrics(
    _: Annotated[UserPublic, Depends(admin_user)],
    engine: Annotated[Component4RankingEngine, Depends(engine_dependency)],
) -> Component4RuntimeMetricsResponse:
    return Component4RuntimeMetricsResponse.model_validate(
        component4_runtime_telemetry.snapshot(
            engine.status()["component_version"],
        )
    )


@router.get("/weights/{category}", response_model=Component4WeightResponse)
async def active_weights(
    category: str,
    engine: Annotated[Component4RankingEngine, Depends(engine_dependency)],
) -> Component4WeightResponse:
    return Component4WeightResponse.model_validate(engine.weight_profile(category))


@router.get("/health", response_model=Component4HealthResponse)
async def component4_health(
    engine: Annotated[Component4RankingEngine, Depends(engine_dependency)],
) -> Component4HealthResponse:
    database_ready = await FirebaseDatabase.ping()
    health = Component4HealthResponse(
        ready=engine.ready and database_ready,
        database_ready=database_ready,
        artifacts_ready=engine.ready,
        provider_score_count=len(engine.provider_scores),
        component_version=engine.status()["component_version"],
        detail="Component 4 is ready" if database_ready else "Firebase RTDB is unavailable",
    )
    if not health.ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=health.detail,
        )
    return health
