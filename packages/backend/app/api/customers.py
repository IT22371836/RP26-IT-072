from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import get_customer_profile_repository, require_role
from app.repositories.customers import CustomerProfileRepository
from app.schemas.auth import UserPublic
from app.schemas.common import UserRole, new_public_id, utc_now
from app.schemas.customer import CustomerProfilePublic, CustomerProfileUpdate

router = APIRouter(prefix="/customers", tags=["customers"])
customer_user = require_role(UserRole.CUSTOMER)


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
    updates = {**payload.model_dump(), "updated_at": utc_now()}
    document = await repository.update_by_user_id(current_user.user_id, updates)
    if document is None:
        raise RuntimeError("Customer profile disappeared during update")
    return CustomerProfilePublic.model_validate(document)
