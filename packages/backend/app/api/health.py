from typing import Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.core.database import MongoDatabase

router = APIRouter(prefix="/health", tags=["health"])


class HealthResponse(BaseModel):
    status: Literal["ok"]


class ReadinessResponse(HealthResponse):
    database: Literal["connected"]


@router.get("/live", response_model=HealthResponse)
async def liveness() -> HealthResponse:
    """Confirm that the API process is running."""

    return HealthResponse(status="ok")


@router.get("/ready", response_model=ReadinessResponse)
async def readiness() -> ReadinessResponse:
    """Confirm that the API can communicate with MongoDB."""

    if not await MongoDatabase.ping():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is unavailable",
        )
    return ReadinessResponse(status="ok", database="connected")
