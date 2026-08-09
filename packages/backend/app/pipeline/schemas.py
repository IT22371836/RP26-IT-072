from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from app.components.component2.schemas import ServiceTime
from app.schemas.common import Urgency


class PipelineStatus(StrEnum):
    INITIALIZING = "initializing"
    CREATED = "created"
    COMPONENT1_RUNNING = "component1_running"
    COMPONENT1_COMPLETED = "component1_completed"
    COMPONENT2_RUNNING = "component2_running"
    COMPONENT2_COMPLETED = "component2_completed"
    COMPONENT4_RUNNING = "component4_running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRY_PENDING = "retry_pending"
    CANCELLED = "cancelled"


TERMINAL_STATUSES = {
    PipelineStatus.COMPLETED.value,
    PipelineStatus.FAILED.value,
    PipelineStatus.CANCELLED.value,
}


class PipelineRunCreate(BaseModel):
    request_text: str = Field(min_length=10, max_length=2000)
    category: str = Field(min_length=2, max_length=100)
    district: str = Field(min_length=2, max_length=100)
    city: str = Field(min_length=2, max_length=100)
    urgency: Urgency = Urgency.NORMAL
    service_date: date
    service_time: ServiceTime
    location_type: Literal["indoor", "outdoor", "indoor and outdoor"]

    @field_validator("request_text", "category", "district", "city")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return " ".join(value.split())


class PipelineStartResponse(BaseModel):
    run_id: str
    request_id: str
    status: PipelineStatus
    status_url: str
    created_at: datetime


class PipelineRunResponse(BaseModel):
    run_id: str
    request_id: str
    user_id: str
    status: PipelineStatus
    request: dict[str, Any]
    component1: dict[str, Any] | None = None
    component2: dict[str, Any] | None = None
    component4: dict[str, Any] | None = None
    fallback: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    selected_provider_id: str | None = None
    booking_interaction_id: str | None = None
    attempt_count: int = 0
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None


class PipelineSelectionRequest(BaseModel):
    provider_id: str = Field(pattern=r"^P[A-Z0-9]+$", min_length=2, max_length=64)


class PipelineSelectionResponse(BaseModel):
    run_id: str
    request_id: str
    provider_id: str
    booking_interaction_id: str
    status: Literal["booking_requested"] = "booking_requested"
