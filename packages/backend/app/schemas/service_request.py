from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.common import Urgency


class ServiceRequestCreate(BaseModel):
    request_text: str = Field(min_length=10, max_length=2000)
    category: str = Field(min_length=2, max_length=100)
    district: str = Field(min_length=2, max_length=100)
    city: str = Field(min_length=2, max_length=100)
    urgency: Urgency = Urgency.NORMAL

    @field_validator("request_text", "category", "district", "city")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return " ".join(value.split())


class ServiceRequestPublic(ServiceRequestCreate):
    model_config = ConfigDict(from_attributes=True)

    request_id: str
    user_id: str
    created_at: datetime


class ServiceRequestDatasetRecord(ServiceRequestPublic):
    """Exact contract of the Component 1 user-request research dataset."""

    pass
