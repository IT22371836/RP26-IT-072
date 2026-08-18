from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_customer_profile_repository, require_firebase_role
from app.repositories.concurrency import ProfileConcurrencyError
from app.repositories.customers import CustomerProfileRepository
from app.schemas.auth import UserPublic
from app.schemas.common import UserRole, new_public_id, utc_now
from app.schemas.customer import CustomerProfilePublic, CustomerProfileUpdate

router = APIRouter(prefix="/customers", tags=["customers"])
customer_user = require_firebase_role(UserRole.CUSTOMER)


async def ensure_customer_profile(user_id: str, repository: CustomerProfileRepository) -> dict:
    document = await repository.find_by_user_id(user_id)
    if document is not None:
        return document
    now = utc_now()
    document = {
        "customer_id": new_public_id("C"),
        "user_id": user_id,
        "phone": None,
        "district": None,
        "city": None,
        "preferred_language": "English",
        "location": None,
        "customer_image": None,
        "created_at": now,
        "updated_at": now,
    }
    await repository.create(document)
    return document


@router.get("/me", response_model=CustomerProfilePublic)
async def get_my_customer_profile(
    current_user: Annotated[UserPublic, Depends(customer_user)],
    repository: Annotated[CustomerProfileRepository, Depends(get_customer_profile_repository)],
) -> CustomerProfilePublic:
    document = await ensure_customer_profile(current_user.user_id, repository)
    return CustomerProfilePublic.model_validate(document)


@router.patch("/me", response_model=CustomerProfilePublic)
async def update_my_customer_profile(
    payload: CustomerProfileUpdate,
    current_user: Annotated[UserPublic, Depends(customer_user)],
    repository: Annotated[CustomerProfileRepository, Depends(get_customer_profile_repository)],
) -> CustomerProfilePublic:
    await ensure_customer_profile(current_user.user_id, repository)
    updates = {
        **payload.model_dump(exclude_unset=True, exclude={"expected_updated_at"}),
        "updated_at": utc_now(),
    }
    try:
        if payload.expected_updated_at is None:
            document = await repository.update_by_user_id(current_user.user_id, updates)
        else:
            document = await repository.update_by_user_id(
                current_user.user_id,
                updates,
                expected_updated_at=payload.expected_updated_at,
            )
    except ProfileConcurrencyError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Customer profile changed; reload it before saving",
        ) from error
    if document is None:
        raise RuntimeError("Customer profile disappeared during update")
    return CustomerProfilePublic.model_validate(document)
