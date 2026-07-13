from app.core.config import Settings
from app.core.security import create_access_token, hash_password, verify_password
from app.repositories.users import UserRepository
from app.schemas.auth import LoginRequest, RegistrationBase, TokenResponse, UserPublic
from app.schemas.common import UserRole, new_public_id, utc_now


class InvalidCredentialsError(Exception):
    pass


class InactiveUserError(Exception):
    pass


class AuthService:
    def __init__(self, repository: UserRepository, settings: Settings) -> None:
        self.repository = repository
        self.settings = settings

    async def register(self, payload: RegistrationBase, role: UserRole) -> UserPublic:
        document = {
            "user_id": new_public_id("U"),
            "email": str(payload.email).lower(),
            "full_name": payload.full_name,
            "hashed_password": hash_password(payload.password),
            "role": role.value,
            "is_active": True,
            "created_at": utc_now(),
        }
        await self.repository.create(document)
        return UserPublic.model_validate(document)

    async def login(self, payload: LoginRequest) -> TokenResponse:
        document = await self.repository.find_by_email(str(payload.email))
        if document is None or not verify_password(
            payload.password, document["hashed_password"]
        ):
            raise InvalidCredentialsError
        if not document.get("is_active", True):
            raise InactiveUserError

        user = UserPublic.model_validate(document)
        token, expires_in = create_access_token(user.user_id, user.role, self.settings)
        return TokenResponse(access_token=token, expires_in=expires_in, user=user)
