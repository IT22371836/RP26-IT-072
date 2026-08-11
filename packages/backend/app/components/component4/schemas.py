from datetime import datetime
from typing import Literal, Self

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.provider_identity import is_supported_provider_id

ASPECTS = ("quality", "punctuality", "communication", "professionalism")


Component4Source = Literal[
    "component2",
    "component2_zero_fallback",
    "development_fixture",
]


class Component4RankRequest(BaseModel):
    source: Component4Source
    request_id: str = Field(pattern=r"^R[A-Z0-9]+$", min_length=2, max_length=64)
    user_id: str = Field(pattern=r"^U[A-Z0-9]+$", min_length=2, max_length=64)
    component_version: str = Field(min_length=1, max_length=128)
    model_version: str = Field(min_length=1, max_length=128)
    provider_ids: list[str] = Field(min_length=1, max_length=10)
    top_k: int = Field(default=5, ge=1, le=5)
    force_recalculate: bool = False

    @field_validator("component_version", "model_version")
    @classmethod
    def normalize_version(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("handoff versions must not be blank")
        return normalized

    @field_validator("provider_ids")
    @classmethod
    def normalize_unique_provider_ids(cls, values: list[str]) -> list[str]:
        normalized = []
        for value in values:
            candidate = value.strip()
            if (
                len(candidate) < 20
                and candidate[:1].lower() == "p"
                and candidate[1:].isalnum()
            ):
                candidate = candidate.upper()
            normalized.append(candidate)
        if any(not is_supported_provider_id(value) for value in normalized):
            raise ValueError("provider_ids must be canonical P IDs or Firebase UIDs")
        if len(normalized) != len(set(normalized)):
            raise ValueError("provider_ids must be unique")
        return normalized

    @model_validator(mode="after")
    def reject_placeholder_component2_versions(self) -> Self:
        if self.source in {"component2", "component2_zero_fallback"} and (
            self.component_version == "not-component2"
            or self.model_version == "not-component2"
        ):
            raise ValueError("real Component 2 handoffs require real version identifiers")
        return self


class Component4HandoffLineage(BaseModel):
    source: Component4Source
    request_id: str
    user_id: str
    component_version: str
    model_version: str


class AspectScores(BaseModel):
    quality: float = Field(ge=-1, le=1)
    punctuality: float = Field(ge=-1, le=1)
    communication: float = Field(ge=-1, le=1)
    professionalism: float = Field(ge=-1, le=1)


class Component4Versions(BaseModel):
    catf_version: str
    weight_version: str
    category_prior_version: str
    absa_model_version: str
    credibility_model_version: str


class RankedProvider(BaseModel):
    provider_id: str
    provider_name: str
    category: str
    district: str
    city: str
    rank: int = Field(ge=1, le=5)
    final_score: float = Field(ge=0, le=1)
    aspect_scores: AspectScores
    mean_credibility: float = Field(ge=0, le=1)
    review_count: int = Field(ge=0)
    effective_review_count: float = Field(ge=0)
    reliability_factor: float = Field(ge=0, le=1)
    evidence_status: Literal["insufficient", "limited", "sufficient"]
    score_source: Literal["catf_evidence", "category_prior"]
    platform_rating: float = Field(ge=0, le=5)
    platform_review_count: int = Field(ge=0)
    ranking_reason: str | None = None


class Component4RankResponse(BaseModel):
    component_version: str
    request_id: str
    run_id: str
    user_id: str
    handoff: Component4HandoffLineage
    input_count: int = Field(ge=1, le=10)
    output_count: int = Field(ge=1, le=5)
    requested_top_k: int = Field(ge=1, le=5)
    candidate_provider_ids: list[str]
    providers: list[RankedProvider]
    versions: Component4Versions
    cached: bool
    processing_time_ms: float = Field(ge=0)


class Component4ModelsResponse(BaseModel):
    ready: bool
    component_version: str
    provider_score_count: int = Field(ge=0)
    versions: Component4Versions
    weight_validation_status: str
    evaluation_version: str | None
    ranking_ground_truth_validation: str
    production_ground_truth_validation: str


class Component4IntegrationReadinessResponse(BaseModel):
    phase: Literal["phase9"]
    status: Literal["awaiting_component2"]
    component4_ready: bool
    component2_connected: bool
    production_ready: bool
    contract_version: str
    expected_source: Literal["component2"]
    maximum_input_candidates: Literal[10]
    maximum_output_providers: Literal[5]
    fixture_policy: Literal["development_only"]
    required_handoff_fields: list[str]
    detail: str


class Component4TimingSummary(BaseModel):
    p50_ms: float = Field(ge=0)
    p95_ms: float = Field(ge=0)
    p99_ms: float = Field(ge=0)
    maximum_ms: float = Field(ge=0)
    total_ms: float = Field(ge=0)
    operations_per_second: float = Field(gt=0)


class Component4PerformanceSummary(BaseModel):
    cold_load_ms: float = Field(ge=0)
    sequential: Component4TimingSummary
    concurrent: Component4TimingSummary


class Component4ReleaseReadinessResponse(BaseModel):
    phase: Literal["phase10"]
    release_evidence_version: str
    status: Literal["component4_ready_awaiting_component2_uat"]
    component4_operationally_ready: bool
    component2_connected: bool
    production_ready: bool
    checks: dict[str, bool]
    performance: Component4PerformanceSummary
    thresholds: dict[str, float]
    remaining_production_gates: list[str]
    detail: str


class Component4HandoffReadinessResponse(BaseModel):
    phase: Literal["phase11"]
    status: Literal["contract_ready_awaiting_component2"]
    contract_version: Literal["component2-to-component4-v1"]
    contract_enforced: bool
    identity_binding_enforced: bool
    lineage_persistence_enabled: bool
    fixture_blocked_in_production: bool
    component2_connected: bool
    production_ready: bool
    required_handoff_fields: list[str]
    detail: str


class Component4RuntimeMetricsResponse(BaseModel):
    scope: Literal["process_local"]
    component_version: str
    started_at: datetime
    uptime_seconds: float = Field(ge=0)
    requests_total: int = Field(ge=0)
    successful_requests: int = Field(ge=0)
    client_errors: int = Field(ge=0)
    server_errors: int = Field(ge=0)
    cache_hits: int = Field(ge=0)
    fresh_rankings: int = Field(ge=0)
    cache_hit_ratio: float = Field(ge=0, le=1)
    average_latency_ms: float = Field(ge=0)
    maximum_latency_ms: float = Field(ge=0)
    latency_buckets: dict[str, int]
    contains_personal_data: Literal[False]
    reset_on_process_restart: Literal[True]


class Component4FinalReadinessResponse(BaseModel):
    phase: Literal["phase12"]
    status: Literal["component4_release_candidate_external_gates_pending"]
    component4_release_candidate_ready: bool
    component2_connected: bool
    external_api_load_test_passed: bool
    production_ready: bool
    checks: dict[str, bool]
    pending_external_gates: list[str]
    detail: str


class Component4WeightResponse(BaseModel):
    category: str
    weights: dict[str, float]
    profile_source: Literal["category_profile", "default_profile"]
    weight_version: str
    validation_status: str


class Component4HealthResponse(BaseModel):
    ready: bool
    database_ready: bool
    artifacts_ready: bool
    provider_score_count: int = Field(ge=0)
    component_version: str
    detail: str
