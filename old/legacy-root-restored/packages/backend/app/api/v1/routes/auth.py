from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.security import decode_access_token
from app.schemas.auth import CurrentUser, LoginRequest, RegisterRequest, TokenResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])
security = HTTPBearer()


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

@router.post("/login/customer", response_model=TokenResponse)
async def customer_login(payload: LoginRequest) -> TokenResponse:
    return await AuthService.login(payload.email, payload.password, "customer")


@router.post("/login/provider", response_model=TokenResponse)
async def provider_login(payload: LoginRequest) -> TokenResponse:
    return await AuthService.login(payload.email, payload.password, "provider")


# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------

@router.post("/register/customer", response_model=TokenResponse, status_code=201)
async def customer_register(payload: RegisterRequest) -> TokenResponse:
    return await AuthService.register(payload, "customer")


@router.post("/register/provider", response_model=TokenResponse, status_code=201)
async def provider_register(payload: RegisterRequest) -> TokenResponse:
    return await AuthService.register(payload, "provider")


# ---------------------------------------------------------------------------
# Current User
# ---------------------------------------------------------------------------

@router.get("/me", response_model=CurrentUser)
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> CurrentUser:
    claims = decode_access_token(credentials.credentials)
    return CurrentUser(
        email=claims["sub"],
        role=claims["role"],
        full_name=claims.get("full_name", ""),
        exp=datetime.fromtimestamp(claims["exp"], tz=UTC),
    )
