from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash

from app.core.config import Settings
from app.schemas.common import UserRole

password_hash = PasswordHash.recommended()


class InvalidAccessTokenError(Exception):
    pass


@dataclass(frozen=True)
class AccessTokenClaims:
    user_id: str
    role: UserRole
    auth_version: int


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return password_hash.verify(password, hashed_password)


def create_access_token(
    user_id: str,
    role: UserRole,
    settings: Settings,
    *,
    auth_version: int = 1,
) -> tuple[str, int]:
    expires_in = settings.jwt_access_token_expire_minutes * 60
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": user_id,
        "role": role.value,
        "ver": auth_version,
        "iat": now,
        "exp": now + timedelta(seconds=expires_in),
    }
    return (
        jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm),
        expires_in,
    )


def decode_access_token_claims(token: str, settings: Settings) -> AccessTokenClaims:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        user_id = payload.get("sub")
        role = UserRole(payload.get("role"))
        auth_version = payload.get("ver", 1)
        if not isinstance(user_id, str) or not user_id:
            raise InvalidAccessTokenError
        if not isinstance(auth_version, int) or isinstance(auth_version, bool):
            raise InvalidAccessTokenError
    except (InvalidTokenError, ValueError, TypeError) as error:
        raise InvalidAccessTokenError from error
    return AccessTokenClaims(
        user_id=user_id,
        role=role,
        auth_version=auth_version,
    )


def decode_access_token(token: str, settings: Settings) -> tuple[str, UserRole]:
    claims = decode_access_token_claims(token, settings)
    return claims.user_id, claims.role
