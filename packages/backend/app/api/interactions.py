from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.dependencies import get_interaction_repository, require_role
from app.repositories.interactions import InteractionRepository
from app.schemas.auth import UserPublic
from app.schemas.common import UserRole, new_public_id, utc_now
from app.schemas.interaction import InteractionCreate, InteractionPublic

router = APIRouter(prefix="/interactions", tags=["interactions"])
customer_user = require_role(UserRole.CUSTOMER)


@router.post("", response_model=InteractionPublic, status_code=status.HTTP_201_CREATED)
async def create_interaction(
    payload: InteractionCreate,
    current_user: Annotated[UserPublic, Depends(customer_user)],
    repository: Annotated[InteractionRepository, Depends(get_interaction_repository)],
) -> InteractionPublic:
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
