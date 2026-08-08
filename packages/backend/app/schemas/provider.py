from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, EmailStr, Field, field_validator


class ProviderLocation(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class ProviderDaySchedule(BaseModel):
    is_open: bool = Field(validation_alias=AliasChoices("is_open", "isOpen"))
    start: str = Field(max_length=20)
    end: str = Field(max_length=20)


class ProviderWorkingHours(BaseModel):
    monday: ProviderDaySchedule = Field(validation_alias=AliasChoices("monday", "Monday"))
    tuesday: ProviderDaySchedule = Field(validation_alias=AliasChoices("tuesday", "Tuesday"))
    wednesday: ProviderDaySchedule = Field(
        validation_alias=AliasChoices("wednesday", "Wednesday")
    )
    thursday: ProviderDaySchedule = Field(
        validation_alias=AliasChoices("thursday", "Thursday")
    )
    friday: ProviderDaySchedule = Field(validation_alias=AliasChoices("friday", "Friday"))
    saturday: ProviderDaySchedule = Field(
        validation_alias=AliasChoices("saturday", "Saturday")
    )
    sunday: ProviderDaySchedule = Field(validation_alias=AliasChoices("sunday", "Sunday"))


class ProviderDocumentCategory(StrEnum):
    IDENTITY_DOCUMENT = "identity_document"
    CERTIFICATION = "certification"
    BUSINESS_REGISTRATION = "business_registration"
    EXPERIENCE_PROOF = "experience_proof"
    PORTFOLIO_WORK = "portfolio_work"


class ProviderDocumentCreate(BaseModel):
    file_id: str | None = Field(
        default=None,
        min_length=2,
        max_length=100,
        validation_alias=AliasChoices("file_id", "fileId"),
    )
    file_name: str = Field(
        min_length=1,
        max_length=255,
        validation_alias=AliasChoices("file_name", "fileName"),
    )
    file_url: str = Field(
        min_length=1,
        max_length=4096,
        validation_alias=AliasChoices("file_url", "fileUrl"),
    )
    format: Literal["JPG", "PNG", "PDF"]
    legacy_url: str | None = Field(
        default=None,
        max_length=4096,
        validation_alias=AliasChoices("legacy_url", "legacyUrl"),
    )
    current_url: str | None = Field(
        default=None,
        max_length=4096,
        validation_alias=AliasChoices("current_url", "currentUrl"),
    )
    storage_path: str | None = Field(
        default=None,
        max_length=1024,
        validation_alias=AliasChoices("storage_path", "storagePath"),
    )
    content_sha256: str | None = Field(
        default=None,
        pattern=r"^[a-f0-9]{64}$",
        validation_alias=AliasChoices("content_sha256", "contentSha256"),
    )
    content_type: Literal["image/jpeg", "image/png", "application/pdf"] | None = Field(
        default=None,
        validation_alias=AliasChoices("content_type", "contentType"),
    )
    size_bytes: int | None = Field(
        default=None,
        ge=0,
        validation_alias=AliasChoices("size_bytes", "sizeBytes"),
    )

    @field_validator("file_name", "file_url", "legacy_url", "current_url", "storage_path")
    @classmethod
    def normalize_document_text(cls, value: str | None) -> str | None:
        return " ".join(value.split()) if value else value


class ProviderDocumentUpload(BaseModel):
    file_name: str = Field(
        min_length=1,
        max_length=255,
        validation_alias=AliasChoices("file_name", "fileName"),
    )
    data_url: str = Field(
        min_length=32,
        max_length=15_000_000,
        validation_alias=AliasChoices("data_url", "dataUrl"),
    )

    @field_validator("file_name")
    @classmethod
    def normalize_file_name(cls, value: str) -> str:
        return " ".join(value.split())


class ProviderDocumentItem(ProviderDocumentCreate):
    file_id: str
    uploaded_at: datetime
    deleted_at: datetime | None = None


class ProviderDocumentsPrivate(BaseModel):
    status: bool = False
    verified: bool = False
    identity_document: list[ProviderDocumentItem] = Field(default_factory=list)
    certification: list[ProviderDocumentItem] = Field(default_factory=list)
    business_registration: list[ProviderDocumentItem] = Field(default_factory=list)
    experience_proof: list[ProviderDocumentItem] = Field(default_factory=list)
    portfolio_work: list[ProviderDocumentItem] = Field(default_factory=list)


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
    verified: bool = False
    created_at: datetime
    updated_at: datetime


class ProviderProfileUpdate(BaseModel):
    expected_updated_at: datetime | None = Field(
        default=None,
        validation_alias=AliasChoices("expected_updated_at", "expectedUpdatedAt"),
    )
    provider_name: str | None = Field(
        default=None,
        min_length=2,
        max_length=160,
        validation_alias=AliasChoices("provider_name", "fullName"),
    )
    category: str | None = Field(default=None, min_length=2, max_length=100)
    district: str | None = Field(default=None, min_length=2, max_length=100)
    city: str | None = Field(default=None, min_length=2, max_length=100)
    experience_years: int | None = Field(
        default=None,
        ge=0,
        le=80,
        validation_alias=AliasChoices("experience_years", "experienceYears"),
    )
    skills: list[str] | None = Field(default=None, min_length=1, max_length=50)
    description: str | None = Field(default=None, min_length=10, max_length=2000)
    phone: str | None = Field(default=None, min_length=7, max_length=20)
    location: ProviderLocation | None = None
    provider_image: str | None = Field(
        default=None,
        max_length=4096,
        validation_alias=AliasChoices("provider_image", "providerImage"),
    )
    preferred_language: str | None = Field(
        default=None,
        min_length=2,
        max_length=100,
        validation_alias=AliasChoices("preferred_language", "preferredLanguage"),
    )
    nic: str | None = Field(default=None, min_length=5, max_length=50)
    working_hours: ProviderWorkingHours | None = Field(
        default=None,
        validation_alias=AliasChoices("working_hours", "workingHours"),
    )

    @field_validator(
        "provider_name",
        "category",
        "district",
        "city",
        "description",
        "phone",
        "provider_image",
        "preferred_language",
        "nic",
    )
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        return " ".join(value.split()) if value else value

    @field_validator("skills")
    @classmethod
    def normalize_optional_skills(cls, values: list[str] | None) -> list[str] | None:
        if values is None:
            return None
        normalized = list(
            dict.fromkeys(" ".join(value.split()) for value in values if value.strip())
        )
        if not normalized:
            raise ValueError("at least one non-empty skill is required")
        return normalized


class ProviderPrivate(ProviderPublic):
    email: EmailStr | None = None
    phone: str | None = None
    location: ProviderLocation | None = None
    provider_image: str | None = None
    preferred_language: str = "English"
    nic: str | None = None
    working_hours: ProviderWorkingHours | None = None
    verified: bool = False
    documents: ProviderDocumentsPrivate = Field(default_factory=ProviderDocumentsPrivate)


class ProviderAspectPerformance(BaseModel):
    quality: float = Field(ge=0, le=1)
    communication: float = Field(ge=0, le=1)
    professionalism: float = Field(ge=0, le=1)
    punctuality: float = Field(ge=0, le=1)


class ProviderCustomerReview(BaseModel):
    rating: int = Field(ge=1, le=5)
    review_text: str | None
    reviewed_at: datetime
    verified_booking: bool
    source: Literal["platform", "research_dataset"]
    credibility_score: float | None = Field(default=None, ge=0, le=1)


class ProviderTrustProfile(BaseModel):
    provider_id: str
    provider_name: str
    category: str
    district: str
    city: str
    description: str
    skills: list[str]
    experience_years: int = Field(ge=0)
    average_rating: float = Field(ge=0, le=5)
    review_count: int = Field(ge=0)
    overall_trust_score: float = Field(ge=0, le=1)
    aspect_performance: ProviderAspectPerformance
    mean_review_credibility: float = Field(ge=0, le=1)
    analyzed_review_count: int = Field(ge=0)
    evidence_status: Literal["insufficient", "limited", "sufficient"]
    score_source: Literal["catf_evidence", "category_prior"]
    customer_reviews: list[ProviderCustomerReview]


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
