from typing import Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.core.firebase_database import FirebaseDatabase

router = APIRouter(prefix="/health", tags=["health"])


class HealthResponse(BaseModel):
    status: Literal["ok"]


class ReadinessResponse(HealthResponse):
    database: Literal["firebase-connected"]


@router.get("/live", response_model=HealthResponse)
async def liveness() -> HealthResponse:
    """Confirm that the API process is running."""

    return HealthResponse(status="ok")


@router.get("/ready", response_model=ReadinessResponse)
async def readiness() -> ReadinessResponse:
    """Confirm that the API can communicate with Firebase RTDB."""

    if not await FirebaseDatabase.ping():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is unavailable",
        )
    return ReadinessResponse(status="ok", database="firebase-connected")
