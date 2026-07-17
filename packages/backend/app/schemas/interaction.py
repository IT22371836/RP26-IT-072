from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class InteractionType(StrEnum):
    IMPRESSION = "impression"
    CLICK = "click"
    SELECTED = "selected"
    BOOKING_REQUESTED = "booking_requested"
    BOOKING_COMPLETED = "booking_completed"
    BOOKING_CANCELLED = "booking_cancelled"
    RATED = "rated"


class InteractionCreate(BaseModel):
    request_id: str
    provider_id: str
    category: str
    provider_name: str | None = None
    interaction_type: InteractionType
    rating: int | None = Field(default=None, ge=1, le=5)


class InteractionPublic(InteractionCreate):
    model_config = ConfigDict(from_attributes=True)

    interaction_id: str
    user_id: str
    timestamp: datetime


class InteractionDatasetRecord(BaseModel):
    """Exact contract of the Component 1 interaction research dataset."""

    interaction_id: str
    user_id: str
    provider_id: str
    category: str
    interaction_type: str
    rating: int = Field(ge=1, le=5)
    booking_status: str
    timestamp: datetime
