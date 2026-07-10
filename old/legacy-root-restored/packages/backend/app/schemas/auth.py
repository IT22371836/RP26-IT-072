from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, field_validator

UserRole = Literal["customer", "provider"]


# ---------------------------------------------------------------------------
# Auth / Login schemas
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: UserRole
    email: EmailStr
    full_name: str


class CurrentUser(BaseModel):
    email: EmailStr
    role: UserRole
    full_name: str
    exp: datetime


# ---------------------------------------------------------------------------
# Registration schemas
# ---------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    phone: str | None = None
    # Provider-specific optional fields
    business_name: str | None = None
    service_types: list[str] | None = None
    address: str | None = None

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        return v

    @field_validator("full_name")
    @classmethod
    def full_name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Full name cannot be empty")
        return v.strip()


class UserPublic(BaseModel):
    id: str
    email: EmailStr
    role: UserRole
    full_name: str
