import asyncio

from app.core.config import Settings
from app.core.security import create_access_token, hash_password
from app.repositories.users import FirebaseLinkConflictError, UserRepository
from app.schemas.auth import FirebaseAccountLinkRequest, TokenResponse, UserPublic
from app.schemas.common import UserRole, utc_now
from app.services.firebase_identity import (
    FirebaseIdentityConfigurationError,
    FirebaseIdentityError,
    FirebaseTokenVerifier,
)


class AccountLinkNotFoundError(Exception):
    pass


class AmbiguousAccountLinkError(Exception):
    pass


class AccountAlreadyLinkedError(Exception):
    pass


class AccountLinkForbiddenError(Exception):
    pass


class AccountLinkService:
    def __init__(
        self,
        repository: UserRepository,
        settings: Settings,
        verifier: FirebaseTokenVerifier,
    ) -> None:
        self.repository = repository
        self.settings = settings
        self.verifier = verifier

    async def link(self, payload: FirebaseAccountLinkRequest) -> TokenResponse:
        identity = await asyncio.to_thread(
            self.verifier.verify,
            payload.firebase_id_token,
        )
        already_linked = await self.repository.find_by_firebase_uid(identity.uid)
        if already_linked is not None:
            raise AccountAlreadyLinkedError

        matches = await self.repository.find_all_by_email(identity.email, limit=2)
        if not matches:
            raise AccountLinkNotFoundError
        if len(matches) != 1:
            raise AmbiguousAccountLinkError

        user_document = matches[0]
        if user_document.get("is_active") is False:
            raise AccountLinkForbiddenError
        role = UserRole(user_document["role"])
        if role not in {UserRole.CUSTOMER, UserRole.PROVIDER}:
            raise AccountLinkForbiddenError

        auth_version = int(user_document.get("auth_version", 1)) + 1
        now = utc_now()
        try:
            linked = await self.repository.link_firebase_identity(
                str(user_document["user_id"]),
                identity.uid,
                identity.email,
                hash_password(payload.new_password),
                now,
                auth_version,
            )
        except FirebaseLinkConflictError as error:
            raise AccountAlreadyLinkedError from error

        user = UserPublic.model_validate(linked)
        token, expires_in = create_access_token(
            user.user_id,
            user.role,
            self.settings,
            auth_version=auth_version,
        )
        return TokenResponse(access_token=token, expires_in=expires_in, user=user)


__all__ = [
    "AccountAlreadyLinkedError",
    "AccountLinkForbiddenError",
    "AccountLinkNotFoundError",
    "AccountLinkService",
    "AmbiguousAccountLinkError",
    "FirebaseIdentityConfigurationError",
    "FirebaseIdentityError",
]
