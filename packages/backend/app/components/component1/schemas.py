from typing import Literal

from pydantic import BaseModel, Field, field_validator


class RecommendationRequest(BaseModel):
    request_id: str = Field(pattern=r"^R[A-Z0-9]+$", min_length=2, max_length=64)
    query: str = Field(min_length=3, max_length=2000)
    category: str | None = Field(default=None, min_length=2, max_length=100)
    district: str | None = Field(default=None, min_length=2, max_length=100)
    city: str | None = Field(default=None, min_length=2, max_length=100)
    min_rating: float = Field(default=0.0, ge=0, le=5)
    top_k: Literal[20] = 20

    @field_validator("query")
    @classmethod
    def normalize_query(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if len(normalized) < 3:
            raise ValueError("query must contain at least 3 non-whitespace characters")
        return normalized


class ProviderRecommendation(BaseModel):
    provider_id: str
    provider_name: str
    category: str
    district: str
    city: str
    skills: str
    description: str
    experience_years: int
    rating: float
    review_count: int
    booking_success_rate: float
    interaction_count: int
    hybrid_score: float = Field(ge=0, le=1)
    tfidf_score: float = Field(ge=0, le=1)
    bert_score: float = Field(ge=0, le=1)
    cf_score: float = Field(ge=0, le=1)
    selection_tier: str | None = None
    selection_reason: str | None = None


class RecommendationResponse(BaseModel):
    component_version: str
    model_version: str
    request_id: str
    query: str
    user_id: str
    results: list[ProviderRecommendation]


class ComponentStatusResponse(BaseModel):
    ready: bool
    component_version: str | None = None
    model_version: str | None = None
    provider_count: int | None = None
    detail: str | None = None
