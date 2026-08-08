from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class LegacyPreservingModel(BaseModel):
    """Validation model for migrated data; unknown source attributes survive round trips."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)


class IntegrationMetadata(LegacyPreservingModel):
    migration_version: str | None = None
    source_system: str | None = None
    last_synced_at: datetime | None = None


class IntegrationLocation(LegacyPreservingModel):
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)


class IntegrationDaySchedule(LegacyPreservingModel):
    is_open: bool | None = Field(
        default=None,
        validation_alias=AliasChoices("is_open", "isOpen"),
        serialization_alias="isOpen",
    )
    start: str | None = None
    end: str | None = None


class IntegrationWorkingHours(LegacyPreservingModel):
    monday: IntegrationDaySchedule | None = Field(
        default=None,
        validation_alias=AliasChoices("monday", "Monday"),
        serialization_alias="Monday",
    )
    tuesday: IntegrationDaySchedule | None = Field(
        default=None,
        validation_alias=AliasChoices("tuesday", "Tuesday"),
        serialization_alias="Tuesday",
    )
    wednesday: IntegrationDaySchedule | None = Field(
        default=None,
        validation_alias=AliasChoices("wednesday", "Wednesday"),
        serialization_alias="Wednesday",
    )
    thursday: IntegrationDaySchedule | None = Field(
        default=None,
        validation_alias=AliasChoices("thursday", "Thursday"),
        serialization_alias="Thursday",
    )
    friday: IntegrationDaySchedule | None = Field(
        default=None,
        validation_alias=AliasChoices("friday", "Friday"),
        serialization_alias="Friday",
    )
    saturday: IntegrationDaySchedule | None = Field(
        default=None,
        validation_alias=AliasChoices("saturday", "Saturday"),
        serialization_alias="Saturday",
    )
    sunday: IntegrationDaySchedule | None = Field(
        default=None,
        validation_alias=AliasChoices("sunday", "Sunday"),
        serialization_alias="Sunday",
    )


class IntegrationProviderDocument(LegacyPreservingModel):
    file_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("file_id", "fileId"),
        serialization_alias="fileId",
    )
    file_name: str | None = Field(
        default=None,
        validation_alias=AliasChoices("file_name", "fileName"),
        serialization_alias="fileName",
    )
    file_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("file_url", "fileUrl"),
        serialization_alias="fileUrl",
    )
    legacy_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("legacy_url", "legacyUrl"),
        serialization_alias="legacyUrl",
    )
    current_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("current_url", "currentUrl"),
        serialization_alias="currentUrl",
    )
    storage_path: str | None = Field(
        default=None,
        validation_alias=AliasChoices("storage_path", "storagePath"),
        serialization_alias="storagePath",
    )
    content_sha256: str | None = Field(
        default=None,
        validation_alias=AliasChoices("content_sha256", "contentSha256"),
        serialization_alias="contentSha256",
    )
    content_type: str | None = Field(
        default=None,
        validation_alias=AliasChoices("content_type", "contentType"),
        serialization_alias="contentType",
    )
    size_bytes: int | None = Field(
        default=None,
        validation_alias=AliasChoices("size_bytes", "sizeBytes"),
        serialization_alias="sizeBytes",
    )
    format: str | None = None
    uploaded_at: str | datetime | None = Field(
        default=None,
        validation_alias=AliasChoices("uploaded_at", "uploadedAt"),
        serialization_alias="uploadedAt",
    )


class IntegrationProviderDocuments(LegacyPreservingModel):
    status: bool | None = None
    verified: bool | None = None
    identity_document: list[IntegrationProviderDocument] | None = Field(
        default=None,
        validation_alias=AliasChoices("identity_document", "identityDocument"),
        serialization_alias="identityDocument",
    )
    certification: list[IntegrationProviderDocument] | None = None
    business_registration: list[IntegrationProviderDocument] | None = Field(
        default=None,
        validation_alias=AliasChoices("business_registration", "businessRegistration"),
        serialization_alias="businessRegistration",
    )
    experience_proof: list[IntegrationProviderDocument] | None = Field(
        default=None,
        validation_alias=AliasChoices("experience_proof", "experienceProof"),
        serialization_alias="experienceProof",
    )
    portfolio_work: list[IntegrationProviderDocument] | None = Field(
        default=None,
        validation_alias=AliasChoices("portfolio_work", "portfolioWork"),
        serialization_alias="portfolioWork",
    )


class IntegrationCredibility(LegacyPreservingModel):
    credibility_level: str | None = Field(
        default=None,
        validation_alias=AliasChoices("credibility_level", "credibilityLevel"),
        serialization_alias="credibilityLevel",
    )
    credibility_score: float | None = Field(
        default=None,
        validation_alias=AliasChoices("credibility_score", "credibilityScore"),
        serialization_alias="credibilityScore",
    )
    last_evaluated_at: str | datetime | None = Field(
        default=None,
        validation_alias=AliasChoices("last_evaluated_at", "lastEvaluatedAt"),
        serialization_alias="lastEvaluatedAt",
    )


class IntegrationExtractedFeatures(LegacyPreservingModel):
    provider_id: str | None = None
    service_category: str | None = None
    identity_verified: bool | None = None
    business_registered: bool | None = None
    certification_count: int | None = None
    cert_issuer_reputation: float | str | None = None
    highest_cert_level: str | None = None
    experience_years: float | None = None
    experience_reference_count: int | None = None
    portfolio_count: int | None = None
    portfolio_quality_score: float | None = None
    credibility: IntegrationCredibility | None = None


class ContextServiceTime(LegacyPreservingModel):
    start_time: str | None = None
    end_time: str | None = None


class ContextEvaluatedProvider(LegacyPreservingModel):
    distance_km: float | None = None
    is_available: bool | None = None
    location_type: str | None = None
    provider_id: str | None = None
    provider_location: IntegrationLocation | None = None
    provider_name: str | None = None
    recommendation: str | None = None
    request_id: str | None = None
    service_day: str | None = None
    user_id: str | None = None
    weather_risk: str | None = None
    working_hours_status: str | None = None


class ContextOutputResults(LegacyPreservingModel):
    evaluated_at: str | datetime | None = None
    evaluated_providers: list[ContextEvaluatedProvider] | None = None
    provider_ids: list[str] | None = None
    recommendation: str | None = None
    weather_risk: str | None = None
    weather_summary: str | None = None


class ContextProviderIds(LegacyPreservingModel):
    provider_ids: list[str] | None = None


class ContextFilterResult(LegacyPreservingModel):
    request_id: str | None = None
    user_id: str | None = None
    service_date: str | None = None
    service_time: ContextServiceTime | None = None
    location_type: str | None = None
    is_new_request: bool | None = Field(
        default=None,
        validation_alias=AliasChoices("is_new_request", "isNewRequest"),
        serialization_alias="isNewRequest",
    )
    output_results: ContextOutputResults | None = None
    results: ContextProviderIds | None = None


class WebDto(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)


class IntegrationLocationWeb(IntegrationLocation):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)


class ContextServiceTimeWeb(ContextServiceTime):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)


class ContextEvaluatedProviderWeb(ContextEvaluatedProvider):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    provider_location: IntegrationLocationWeb | None = None


class ContextOutputResultsWeb(ContextOutputResults):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    evaluated_providers: list[ContextEvaluatedProviderWeb] | None = None


class ContextProviderIdsWeb(ContextProviderIds):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)


class ContextFilterResultWeb(BaseModel):
    """Allowlisted administrator DTO; Mongo internals and arbitrary extras are excluded."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    id: str
    request_id: str | None = None
    user_id: str | None = None
    service_date: str | None = None
    service_time: ContextServiceTimeWeb | None = None
    location_type: str | None = None
    is_new_request: bool | None = Field(
        default=None,
        validation_alias=AliasChoices("is_new_request", "isNewRequest"),
        serialization_alias="isNewRequest",
    )
    output_results: ContextOutputResultsWeb | None = None
    results: ContextProviderIdsWeb | None = None


class DailyDemandCategory(LegacyPreservingModel):
    service_category: str | None = None
    monday: float | None = Field(
        default=None,
        validation_alias=AliasChoices("monday", "Monday"),
        serialization_alias="Monday",
    )
    tuesday: float | None = Field(
        default=None,
        validation_alias=AliasChoices("tuesday", "Tuesday"),
        serialization_alias="Tuesday",
    )
    wednesday: float | None = Field(
        default=None,
        validation_alias=AliasChoices("wednesday", "Wednesday"),
        serialization_alias="Wednesday",
    )
    thursday: float | None = Field(
        default=None,
        validation_alias=AliasChoices("thursday", "Thursday"),
        serialization_alias="Thursday",
    )
    friday: float | None = Field(
        default=None,
        validation_alias=AliasChoices("friday", "Friday"),
        serialization_alias="Friday",
    )
    saturday: float | None = Field(
        default=None,
        validation_alias=AliasChoices("saturday", "Saturday"),
        serialization_alias="Saturday",
    )
    sunday: float | None = Field(
        default=None,
        validation_alias=AliasChoices("sunday", "Sunday"),
        serialization_alias="Sunday",
    )
    total_weekly: float | None = None
    avg_daily: float | None = None
    demand_level: str | None = None


class DailyDemandSummary(DailyDemandCategory):
    service_category: str | None = Field(
        default=None,
        validation_alias=AliasChoices("service_category", "Service Category"),
        serialization_alias="Service Category",
    )
    total_weekly: float | None = Field(
        default=None,
        validation_alias=AliasChoices("total_weekly", "Total Weekly Orders"),
        serialization_alias="Total Weekly Orders",
    )
    avg_daily: float | None = Field(
        default=None,
        validation_alias=AliasChoices("avg_daily", "Avg Daily Orders"),
        serialization_alias="Avg Daily Orders",
    )
    demand_level: str | None = Field(
        default=None,
        validation_alias=AliasChoices("demand_level", "Weekly Demand Level"),
        serialization_alias="Weekly Demand Level",
    )


class DailyDemandRecord(LegacyPreservingModel):
    compile_date: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    target_week: str | None = None
    last_updated: str | datetime | None = None
    by_category: dict[str, DailyDemandCategory] | None = None
    summary: list[DailyDemandSummary] | None = None


class DailyDemandCategoryWeb(DailyDemandCategory):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)


class DailyDemandSummaryWeb(DailyDemandSummary):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)


class DailyDemandWebResponse(BaseModel):
    """Allowlisted WEB DTO with Firebase-compatible response names."""

    compile_date: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    target_week: str | None = None
    last_updated: str | datetime | None = None
    by_category: dict[str, DailyDemandCategoryWeb] | None = None
    summary: list[DailyDemandSummaryWeb] | None = None


def dump_preserving_unknown(model: LegacyPreservingModel) -> dict[str, Any]:
    return model.model_dump(by_alias=True, exclude_unset=True)
