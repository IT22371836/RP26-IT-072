from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies import (
    get_current_user,
    get_integration_read_repository,
    require_role,
)
from app.repositories.integration import IntegrationReadRepository
from app.schemas.auth import UserPublic
from app.schemas.common import UserRole
from app.schemas.integration import ContextFilterResultWeb, DailyDemandWebResponse

router = APIRouter(prefix="/integration", tags=["WEB integration"])
admin_user = require_role(UserRole.ADMIN)


@router.get("/daily-demand/current", response_model=DailyDemandWebResponse)
async def get_current_daily_demand(
    _: Annotated[UserPublic, Depends(get_current_user)],
    repository: Annotated[
        IntegrationReadRepository,
        Depends(get_integration_read_repository),
    ],
) -> DailyDemandWebResponse:
    document = await repository.get_current_daily_demand()
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Migrated daily-demand data is not available",
        )
    return DailyDemandWebResponse.model_validate(document)


@router.get("/filter-requests", response_model=list[ContextFilterResultWeb])
async def list_filter_request_history(
    _: Annotated[UserPublic, Depends(admin_user)],
    repository: Annotated[
        IntegrationReadRepository,
        Depends(get_integration_read_repository),
    ],
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[ContextFilterResultWeb]:
    documents = await repository.list_filter_requests(limit)
    return [ContextFilterResultWeb.model_validate(document) for document in documents]
