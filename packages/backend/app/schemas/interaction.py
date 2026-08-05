from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator


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
    review_text: str | None = Field(default=None, max_length=2000)

    @field_validator("review_text")
    @classmethod
    def normalize_review_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split())
        return normalized or None


class InteractionPublic(InteractionCreate):
    model_config = ConfigDict(from_attributes=True)

    interaction_id: str
    user_id: str
    timestamp: datetime


class RatingCreate(BaseModel):
    rating: int = Field(ge=1, le=5)
    review_text: str | None = Field(default=None, max_length=2000)

    @field_validator("review_text")
    @classmethod
    def normalize_review_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split())
        return normalized or None


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
