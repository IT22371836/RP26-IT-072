from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies import get_service_request_repository, require_firebase_role
from app.repositories.service_requests import ServiceRequestRepository
from app.schemas.auth import UserPublic
from app.schemas.common import UserRole, new_public_id, utc_now
from app.schemas.service_request import ServiceRequestCreate, ServiceRequestPublic

router = APIRouter(prefix="/service-requests", tags=["service requests"])
customer_user = require_firebase_role(UserRole.CUSTOMER)


@router.post("", response_model=ServiceRequestPublic, status_code=status.HTTP_201_CREATED)
async def create_service_request(
    payload: ServiceRequestCreate,
    current_user: Annotated[UserPublic, Depends(customer_user)],
    repository: Annotated[ServiceRequestRepository, Depends(get_service_request_repository)],
) -> ServiceRequestPublic:
    document = {
        **payload.model_dump(mode="json"),
        "request_id": new_public_id("R"),
        "user_id": current_user.user_id,
        "created_at": utc_now(),
    }
    await repository.create(document)
    return ServiceRequestPublic.model_validate(document)


@router.get("/me", response_model=list[ServiceRequestPublic])
async def list_my_service_requests(
    current_user: Annotated[UserPublic, Depends(customer_user)],
    repository: Annotated[ServiceRequestRepository, Depends(get_service_request_repository)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[ServiceRequestPublic]:
    documents = await repository.list_for_user(current_user.user_id, limit)
    return [ServiceRequestPublic.model_validate(document) for document in documents]


@router.get("/{request_id}", response_model=ServiceRequestPublic)
async def get_service_request(
    request_id: str,
    current_user: Annotated[UserPublic, Depends(customer_user)],
    repository: Annotated[ServiceRequestRepository, Depends(get_service_request_repository)],
) -> ServiceRequestPublic:
    document = await repository.find_by_id(request_id)
    if document is None or document["user_id"] != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service request not found",
        )
    return ServiceRequestPublic.model_validate(document)
