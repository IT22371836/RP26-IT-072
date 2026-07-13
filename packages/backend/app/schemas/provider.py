from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProviderCreate(BaseModel):
    provider_name: str = Field(min_length=2, max_length=160)
    category: str = Field(min_length=2, max_length=100)
    district: str = Field(min_length=2, max_length=100)
    city: str = Field(min_length=2, max_length=100)
    experience_years: int = Field(ge=0, le=80)
    skills: list[str] = Field(min_length=1, max_length=50)
    description: str = Field(min_length=10, max_length=2000)

    @field_validator("provider_name", "category", "district", "city", "description")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return " ".join(value.split())

    @field_validator("skills")
    @classmethod
    def normalize_skills(cls, values: list[str]) -> list[str]:
        normalized = list(
            dict.fromkeys(" ".join(value.split()) for value in values if value.strip())
        )
        if not normalized:
            raise ValueError("at least one non-empty skill is required")
        return normalized


class ProviderPublic(ProviderCreate):
    model_config = ConfigDict(from_attributes=True)

    provider_id: str
    user_id: str
    rating: float = Field(ge=0, le=5)
    review_count: int = Field(ge=0)
    booking_success_rate: float = Field(ge=0, le=1)
    interaction_count: int = Field(ge=0)
    created_at: datetime
    updated_at: datetime


class ProviderDatasetRecord(BaseModel):
    """Exact contract of the Component 1 provider research dataset."""

    provider_id: str
    provider_name: str
    category: str
    district: str
    city: str
    experience_years: int = Field(ge=0)
    rating: float = Field(ge=0, le=5)
    review_count: int = Field(ge=0)
    booking_success_rate: float = Field(ge=0, le=1)
    interaction_count: int = Field(ge=0)
    skills: str
    description: str
