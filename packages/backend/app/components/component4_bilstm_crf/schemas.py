from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


# ─── Existing ALSA schemas ────────────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    text: str = Field(..., min_length=1)


class AnalyzeBatchRequest(BaseModel):
    texts: list[str] = Field(..., min_length=1)


class TokenTag(BaseModel):
    token: str
    tag: str


class AspectScores(BaseModel):
    QUAL: Optional[float] = None
    PRICE: Optional[float] = None
    TIME: Optional[float] = None
    COMM: Optional[float] = None


class AnalyzeResponse(BaseModel):
    status: str
    text: str
    tokens: list[TokenTag]
    aspects: AspectScores
    timestamp: str


class BatchResultItem(BaseModel):
    text: str
    result: AnalyzeResponse


class AnalyzeBatchResponse(BaseModel):
    status: str
    batch_size: int
    timestamp: str
    results: list[BatchResultItem]


# ─── Fraud detection schemas ──────────────────────────────────────────────────

class ReviewBehavioralFeatures(BaseModel):
    rating: Optional[float] = Field(None, ge=1.0, le=5.0, description="Star rating (1-5)")
    user_total_reviews: int = Field(5, ge=0)
    days_since_prev_review: float = Field(30.0, ge=0.0)
    user_provider_diversity: float = Field(3.0, ge=0.0)
    text_frequency: int = Field(1, ge=1)
    days_since_review: float = Field(30.0, ge=0.0)
    booking_status: int = Field(1, ge=0, le=1)


class ReviewCredibilityRequest(BaseModel):
    text: str = Field(..., min_length=1)
    behavioral: Optional[ReviewBehavioralFeatures] = None


class LinguisticFeatures(BaseModel):
    word_count: int
    unique_word_ratio: float
    pronoun_count: int
    adj_density: float
    exclamation_count: int
    caps_ratio: float
    rating_text_mismatch: float


class ReviewCredibilityResponse(BaseModel):
    status: str
    text: str
    tokens: list[TokenTag]
    aspects: AspectScores
    fraud_score: float
    trust_label: str
    is_suspicious: bool
    linguistic_features: LinguisticFeatures
    timestamp: str


# ─── Provider credibility schemas ─────────────────────────────────────────────

class ProviderCredibilityResponse(BaseModel):
    provider_id: str
    S_final: float
    tier: str
    S_cred: Optional[float] = None
    S_overall: Optional[float] = None
    fraud_ratio: Optional[float] = None
    recency_boost: Optional[float] = None
    avg_rating: Optional[float] = None
    total_reviews: Optional[int] = None
    suspicious_count: Optional[int] = None
    explanation: Optional[str] = None


class ProviderRankEntry(BaseModel):
    rank: int
    provider_id: str
    S_final: Optional[float] = None
    tier: str
    S_cred: Optional[float] = None
    S_overall: Optional[float] = None
    fraud_ratio: Optional[float] = None
    recency_boost: Optional[float] = None
    avg_rating: Optional[float] = None
    total_reviews: Optional[int] = None
    suspicious_count: Optional[int] = None
    explanation: Optional[str] = None


class RankProvidersRequest(BaseModel):
    provider_ids: list[str] = Field(..., min_length=1, max_length=50)


class RankProvidersResponse(BaseModel):
    status: str
    total: int
    ranked: list[ProviderRankEntry]
    timestamp: str


class PipelineRunRequest(BaseModel):
    provider_ids: Optional[list[str]] = Field(None, max_length=20)
    top_n: int = Field(5, ge=1, le=10)


class PipelineRunResponse(BaseModel):
    status: str
    source: str          # "random" | "component3"
    providers_evaluated: int
    top_n: int
    ranked: list[ProviderRankEntry]
    note: str
    timestamp: str
