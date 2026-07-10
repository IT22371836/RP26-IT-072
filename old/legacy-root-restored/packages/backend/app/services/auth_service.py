from datetime import UTC, datetime

from fastapi import HTTPException, status

from app.core.database import get_database
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import UserInDB
from app.repositories.user_repository import UserRepository
from app.schemas.auth import RegisterRequest, TokenResponse, UserRole


class AuthService:
    # ------------------------------------------------------------------
    # Login
    # ------------------------------------------------------------------
    @staticmethod
    async def login(email: str, password: str, expected_role: UserRole) -> TokenResponse:
        db = get_database()
        repo = UserRepository(db)

        user = await repo.find_by_email(email)
        if user is None or user.role != expected_role or not verify_password(password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
            )

        token = create_access_token(
            email=user.email,
            role=expected_role,
            full_name=user.full_name,
        )
        return TokenResponse(
            access_token=token,
            role=expected_role,
            email=user.email,
            full_name=user.full_name,
        )

    # ------------------------------------------------------------------
    # Register
    # ------------------------------------------------------------------
    @staticmethod
    async def register(payload: RegisterRequest, role: UserRole) -> TokenResponse:
        db = get_database()
        repo = UserRepository(db)

        if await repo.email_exists(payload.email):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email already exists",
            )

        new_user = UserInDB(
            id="",  # will be set after insert
            email=payload.email.lower(),
            role=role,
            full_name=payload.full_name,
            password_hash=hash_password(payload.password),
            phone=payload.phone,
            business_name=payload.business_name if role == "provider" else None,
            service_types=payload.service_types if role == "provider" else None,
            address=payload.address if role == "provider" else None,
            created_at=datetime.now(UTC),
        )

        inserted_id = await repo.create_user(new_user)
        new_user.id = inserted_id

        token = create_access_token(
            email=new_user.email,
            role=role,
            full_name=new_user.full_name,
        )
        return TokenResponse(
            access_token=token,
            role=role,
            email=new_user.email,
            full_name=new_user.full_name,
        )
