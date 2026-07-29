from app.core.config import Settings
from app.core.security import (
    InvalidAccessTokenError,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.schemas.common import UserRole


def settings() -> Settings:
    return Settings(
        mongodb_uri="mongodb://localhost:27017",
        mongodb_database="test_database",
        jwt_secret_key="test-secret-that-is-long-enough-for-tests",
    )


def test_password_is_hashed_and_verified() -> None:
    password = "StrongPassword123!"
    hashed = hash_password(password)

    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("incorrect-password", hashed) is False


def test_access_token_round_trip() -> None:
    token, expires_in = create_access_token("U123", UserRole.CUSTOMER, settings())

    assert expires_in == 3600
    assert decode_access_token(token, settings()) == ("U123", UserRole.CUSTOMER)


def test_invalid_access_token_is_rejected() -> None:
    try:
        decode_access_token("not-a-token", settings())
    except InvalidAccessTokenError:
        pass
    else:
        raise AssertionError("invalid token was accepted")
