from typing import Literal

from pydantic import BaseModel, Field, field_validator

ASPECTS = ("quality", "punctuality", "communication", "professionalism")


class Component4RankRequest(BaseModel):
    request_id: str = Field(pattern=r"^R[A-Z0-9]+$", min_length=2, max_length=64)
    provider_ids: list[str] = Field(min_length=1, max_length=10)
    top_k: int = Field(default=5, ge=1, le=5)
    force_recalculate: bool = False

    @field_validator("provider_ids")
    @classmethod
    def normalize_unique_provider_ids(cls, values: list[str]) -> list[str]:
        normalized = [value.strip().upper() for value in values]
        if any(not value.startswith("P") or not value[1:].isalnum() for value in normalized):
            raise ValueError("provider_ids must be canonical IDs beginning with P")
        if len(normalized) != len(set(normalized)):
            raise ValueError("provider_ids must be unique")
        return normalized


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


class Component4RankResponse(BaseModel):
    component_version: str
    request_id: str
    run_id: str
    user_id: str
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
