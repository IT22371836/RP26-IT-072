from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.database import get_database
from app.core.security import decode_access_token
from app.services.maintenance_service import MaintenanceService
from app.schemas.maintenance import CustomerDashboard, ProviderDashboard

router = APIRouter(prefix="/dashboard", tags=["maintenance"])
security = HTTPBearer()


@router.get("/customer", response_model=CustomerDashboard)
async def customer_dashboard(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> CustomerDashboard:
    claims = decode_access_token(credentials.credentials)
    if claims.get("role") != "customer":
        from fastapi import HTTPException, status

        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    customer_email = claims["sub"]
    return await MaintenanceService.get_customer_dashboard(customer_email)


@router.get("/provider", response_model=ProviderDashboard)
async def provider_dashboard(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> ProviderDashboard:
    claims = decode_access_token(credentials.credentials)
    if claims.get("role") != "provider":
        from fastapi import HTTPException, status

        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    provider_email = claims["sub"]
    return await MaintenanceService.get_provider_dashboard(provider_email)
