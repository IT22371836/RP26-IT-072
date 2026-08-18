from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status

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
    FirebaseAccountLinkRequest,
    LoginRequest,
    PasswordChangeRequest,
    ProviderRegistration,
    TokenResponse,
    UserPublic,
)
from app.schemas.common import UserRole, new_public_id, utc_now
from app.services.account_link import (
    AccountAlreadyLinkedError,
    AccountLinkForbiddenError,
    AccountLinkNotFoundError,
    AccountLinkService,
    AmbiguousAccountLinkError,
    FirebaseIdentityConfigurationError,
    FirebaseIdentityError,
)
from app.services.auth import AuthService, InactiveUserError, InvalidCredentialsError
from app.services.firebase_identity import FirebaseTokenVerifier

router = APIRouter(prefix="/auth", tags=["authentication"])


def auth_service(
    repository: Annotated[UserRepository, Depends(get_user_repository)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthService:
    return AuthService(repository, settings)


def account_link_service(
    repository: Annotated[UserRepository, Depends(get_user_repository)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AccountLinkService:
    return AccountLinkService(repository, settings, FirebaseTokenVerifier(settings))


def deliver_token(
    token_response: TokenResponse,
    response: Response,
    settings: Settings,
) -> TokenResponse:
    if not settings.auth_cookie_enabled:
        return token_response
    token = token_response.access_token
    if not token:
        raise RuntimeError("Authentication service did not issue an access token")
    response.set_cookie(
        key=settings.auth_cookie_name,
        value=token,
        max_age=token_response.expires_in,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
        path=settings.api_v1_prefix,
    )
    return token_response.model_copy(
        update={"access_token": None, "token_transport": "cookie"}
    )


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
    response: Response,
    service: Annotated[AuthService, Depends(auth_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    try:
        token_response = await service.login(payload)
    except (InvalidCredentialsError, InactiveUserError) as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        ) from error
    return deliver_token(token_response, response, settings)


@router.post("/link/firebase", response_model=TokenResponse)
async def link_firebase_account(
    payload: FirebaseAccountLinkRequest,
    response: Response,
    service: Annotated[AccountLinkService, Depends(account_link_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    try:
        token_response = await service.link(payload)
    except FirebaseIdentityError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired Firebase identity token",
        ) from error
    except FirebaseIdentityConfigurationError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Firebase account linking is unavailable",
        ) from error
    except AccountLinkNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No eligible backend account matches this Firebase identity",
        ) from error
    except (AmbiguousAccountLinkError, AccountAlreadyLinkedError) as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Firebase identity cannot be linked automatically",
        ) from error
    except AccountLinkForbiddenError as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This backend account is not eligible for Firebase linking",
        ) from error
    return deliver_token(token_response, response, settings)


@router.post("/password", response_model=TokenResponse)
async def change_password(
    payload: PasswordChangeRequest,
    response: Response,
    current_user: Annotated[UserPublic, Depends(get_current_user)],
    service: Annotated[AuthService, Depends(auth_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    try:
        token_response = await service.change_password(current_user.user_id, payload)
    except (InvalidCredentialsError, InactiveUserError) as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Password change could not be authorized",
        ) from error
    return deliver_token(token_response, response, settings)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    response.delete_cookie(
        key=settings.auth_cookie_name,
        path=settings.api_v1_prefix,
        secure=settings.auth_cookie_secure,
        httponly=True,
        samesite=settings.auth_cookie_samesite,
    )


@router.get("/me", response_model=UserPublic)
async def me(current_user: Annotated[UserPublic, Depends(get_current_user)]) -> UserPublic:
    return current_user
