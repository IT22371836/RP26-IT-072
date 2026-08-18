import asyncio
from collections.abc import Callable, Coroutine
from typing import Annotated, Any

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import Settings, get_settings
from app.core.firebase_database import get_database
from app.core.security import InvalidAccessTokenError, decode_access_token_claims
from app.integrations.firebase_component2 import FirebaseComponent2Error, FirebaseRtdbClient
from app.repositories.component1 import Component1Repository
from app.repositories.component4 import Component4Repository
from app.repositories.customers import CustomerProfileRepository
from app.repositories.integration import IntegrationReadRepository
from app.repositories.interactions import InteractionRepository
from app.repositories.pipeline import PipelineRepository
from app.repositories.providers import ProviderRepository
from app.repositories.service_requests import ServiceRequestRepository
from app.repositories.users import FirebaseLinkConflictError, UserRepository
from app.schemas.auth import UserPublic
from app.schemas.common import UserRole, new_public_id, utc_now
from app.services.firebase_identity import (
    FirebaseIdentityConfigurationError,
    FirebaseIdentityError,
    FirebaseTokenVerifier,
)

bearer_scheme = HTTPBearer(auto_error=False)


def get_user_repository(database: Annotated[Any, Depends(get_database)]) -> UserRepository:
    return UserRepository(database)


def get_firebase_token_verifier(
    settings: Annotated[Settings, Depends(get_settings)],
) -> FirebaseTokenVerifier:
    return FirebaseTokenVerifier(settings)


def get_firebase_rtdb_client(
    settings: Annotated[Settings, Depends(get_settings)],
) -> FirebaseRtdbClient:
    return FirebaseRtdbClient(settings)


def get_provider_repository(database: Annotated[Any, Depends(get_database)]) -> ProviderRepository:
    return ProviderRepository(database)


def get_component4_repository(
    database: Annotated[Any, Depends(get_database)],
) -> Component4Repository:
    return Component4Repository(database)


def get_component1_repository(
    database: Annotated[Any, Depends(get_database)],
) -> Component1Repository:
    return Component1Repository(database)


def get_customer_profile_repository(
    database: Annotated[Any, Depends(get_database)],
) -> CustomerProfileRepository:
    return CustomerProfileRepository(database)


def get_interaction_repository(
    database: Annotated[Any, Depends(get_database)],
) -> InteractionRepository:
    return InteractionRepository(database)


def get_pipeline_repository(
    database: Annotated[Any, Depends(get_database)],
) -> PipelineRepository:
    return PipelineRepository(database)


def get_integration_read_repository(
    database: Annotated[Any, Depends(get_database)],
) -> IntegrationReadRepository:
    return IntegrationReadRepository(database)


def get_service_request_repository(
    database: Annotated[Any, Depends(get_database)],
) -> ServiceRequestRepository:
    return ServiceRequestRepository(database)


async def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    repository: Annotated[UserRepository, Depends(get_user_repository)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> UserPublic:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing authentication token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    token = (
        credentials.credentials
        if credentials is not None
        else request.cookies.get(settings.auth_cookie_name)
    )
    if not token:
        raise unauthorized
    try:
        claims = decode_access_token_claims(token, settings)
    except InvalidAccessTokenError as error:
        raise unauthorized from error

    document = await repository.find_by_id(claims.user_id)
    if document is None or not document.get("is_active", True):
        raise unauthorized
    if str(document.get("role")) != claims.role.value:
        raise unauthorized
    if int(document.get("auth_version", 1)) != claims.auth_version:
        raise unauthorized
    return UserPublic.model_validate(document)


def require_role(
    *allowed_roles: UserRole,
) -> Callable[[UserPublic], Coroutine[Any, Any, UserPublic]]:
    async def dependency(
        current_user: Annotated[UserPublic, Depends(get_current_user)],
    ) -> UserPublic:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user

    return dependency


async def get_firebase_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    repository: Annotated[UserRepository, Depends(get_user_repository)],
    settings: Annotated[Settings, Depends(get_settings)],
    verifier: Annotated[FirebaseTokenVerifier, Depends(get_firebase_token_verifier)],
) -> UserPublic:
    """Authorize application APIs exclusively with a Firebase ID token."""

    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing Firebase authentication token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None or not credentials.credentials:
        raise unauthorized
    try:
        identity = await asyncio.to_thread(
            verifier.verify,
            credentials.credentials,
            require_verified_email=False,
        )
    except FirebaseIdentityConfigurationError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Firebase authentication verification is unavailable",
        ) from error
    except FirebaseIdentityError as error:
        detail = {
            "expired": "Firebase session expired. Please sign in again.",
            "revoked": "Firebase session was revoked. Please sign in again.",
            "disabled": "This Firebase account is disabled.",
            "certificate_unavailable": (
                "Firebase authentication verification is temporarily unavailable."
            ),
        }.get(error.reason, unauthorized.detail)
        code = (
            status.HTTP_503_SERVICE_UNAVAILABLE
            if error.reason == "certificate_unavailable"
            else status.HTTP_401_UNAUTHORIZED
        )
        raise HTTPException(
            status_code=code,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"} if code == 401 else None,
        ) from error

    document = await repository.find_by_firebase_uid(identity.uid)
    if document is None:
        try:
            resolved = await FirebaseRtdbClient(settings).get_identity_profile(identity.uid)
        except FirebaseComponent2Error as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Firebase profile lookup is unavailable",
            ) from error
        if resolved is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Firebase account has no customer, provider, or admin profile",
            )
        role, profile = resolved
        profile_email = str(profile.get("email") or "").strip().lower()
        if profile_email and profile_email != identity.email:
            raise unauthorized
        full_name = str(
            profile.get("fullName")
            or profile.get("providerName")
            or profile.get("name")
            or identity.email.split("@", 1)[0]
        ).strip()
        try:
            document = await repository.ensure_firebase_identity(
                firebase_uid=identity.uid,
                email=identity.email,
                full_name=full_name,
                role=role,
                now=utc_now(),
                user_id=new_public_id("U"),
            )
        except FirebaseLinkConflictError as error:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Firebase identity conflicts with an existing ML identity",
            ) from error

    if not document.get("is_active", True):
        raise unauthorized
    return UserPublic.model_validate(document)


def require_firebase_role(
    *allowed_roles: UserRole,
) -> Callable[[UserPublic], Coroutine[Any, Any, UserPublic]]:
    async def dependency(
        current_user: Annotated[UserPublic, Depends(get_firebase_current_user)],
    ) -> UserPublic:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user

    return dependency
