from datetime import UTC, datetime, timedelta
import hashlib
import hmac

import jwt
from fastapi import HTTPException, status

from app.core.config import settings
from app.schemas.auth import UserRole


def _derive_password_hash(password: str) -> str:
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        settings.auth_password_pepper.encode("utf-8"),
        120_000,
    )
    return digest.hex()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return hmac.compare_digest(_derive_password_hash(plain_password), hashed_password)


def hash_password(password: str) -> str:
    return _derive_password_hash(password)


def create_access_token(email: str, role: UserRole, full_name: str = "") -> str:
    expires = datetime.now(UTC) + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    payload = {
        "sub": email,
        "role": role,
        "full_name": full_name,
        "exp": expires,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
        ) from exc
