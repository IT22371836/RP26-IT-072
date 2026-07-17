from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import (
    get_current_user,
    get_customer_profile_repository,
    get_user_repository,
)
from app.core.config import Settings, get_settings
from app.repositories.customers import CustomerProfileRepository
from app.repositories.users import DuplicateEmailError, UserRepository
from app.schemas.auth import (
    CustomerRegistration,
    LoginRequest,
    ProviderRegistration,
    TokenResponse,
    UserPublic,
)
from app.schemas.common import UserRole, new_public_id, utc_now
from app.services.auth import AuthService, InactiveUserError, InvalidCredentialsError

router = APIRouter(prefix="/auth", tags=["authentication"])


def auth_service(
    repository: Annotated[UserRepository, Depends(get_user_repository)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthService:
    return AuthService(repository, settings)


async def register_user(
    payload: CustomerRegistration | ProviderRegistration,
    role: UserRole,
    service: AuthService,
) -> UserPublic:
    try:
        return await service.register(payload, role)
    except DuplicateEmailError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        ) from error


@router.post(
    "/register/customer",
    response_model=UserPublic,
    status_code=status.HTTP_201_CREATED,
)
async def register_customer(
    payload: CustomerRegistration,
    service: Annotated[AuthService, Depends(auth_service)],
    profile_repository: Annotated[
        CustomerProfileRepository, Depends(get_customer_profile_repository)
    ],
) -> UserPublic:
    user = await register_user(payload, UserRole.CUSTOMER, service)
    now = utc_now()
    await profile_repository.create(
        {
            "customer_id": new_public_id("C"),
            "user_id": user.user_id,
            "phone": None,
            "district": None,
            "city": None,
            "preferred_language": "English",
            "created_at": now,
            "updated_at": now,
        }
    )
    return user


@router.post(
    "/register/provider",
    response_model=UserPublic,
    status_code=status.HTTP_201_CREATED,
)
async def register_provider(
    payload: ProviderRegistration,
    service: Annotated[AuthService, Depends(auth_service)],
) -> UserPublic:
    return await register_user(payload, UserRole.PROVIDER, service)


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    service: Annotated[AuthService, Depends(auth_service)],
) -> TokenResponse:
    try:
        return await service.login(payload)
    except (InvalidCredentialsError, InactiveUserError) as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        ) from error


@router.get("/me", response_model=UserPublic)
async def me(current_user: Annotated[UserPublic, Depends(get_current_user)]) -> UserPublic:
    return current_user
