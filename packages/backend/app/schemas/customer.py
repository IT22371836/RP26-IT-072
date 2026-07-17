from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CustomerProfileUpdate(BaseModel):
    phone: str | None = Field(default=None, min_length=7, max_length=20)
    district: str | None = Field(default=None, min_length=2, max_length=100)
    city: str | None = Field(default=None, min_length=2, max_length=100)
    preferred_language: str = Field(default="English", min_length=2, max_length=30)

    @field_validator("phone", "district", "city", "preferred_language")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        return " ".join(value.split()) if value else value


class CustomerProfilePublic(CustomerProfileUpdate):
    model_config = ConfigDict(from_attributes=True)

    customer_id: str
    user_id: str
    created_at: datetime
    updated_at: datetime
