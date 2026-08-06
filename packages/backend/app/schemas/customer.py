from datetime import datetime

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator


class CustomerLocation(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class CustomerProfileUpdate(BaseModel):
    expected_updated_at: datetime | None = Field(
        default=None,
        validation_alias=AliasChoices("expected_updated_at", "expectedUpdatedAt"),
    )
    phone: str | None = Field(default=None, min_length=7, max_length=20)
    district: str | None = Field(default=None, min_length=2, max_length=100)
    city: str | None = Field(default=None, min_length=2, max_length=100)
    preferred_language: str | None = Field(
        default=None,
        min_length=2,
        max_length=30,
        validation_alias=AliasChoices("preferred_language", "preferredLanguage"),
    )
    location: CustomerLocation | None = None
    customer_image: str | None = Field(
        default=None,
        max_length=4096,
        validation_alias=AliasChoices("customer_image", "customerImage"),
    )

    @field_validator("phone", "district", "city", "preferred_language", "customer_image")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        return " ".join(value.split()) if value else value


class CustomerProfilePublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    customer_id: str
    user_id: str
    phone: str | None = None
    district: str | None = None
    city: str | None = None
    preferred_language: str = "English"
    location: CustomerLocation | None = None
    customer_image: str | None = None
    created_at: datetime
    updated_at: datetime
