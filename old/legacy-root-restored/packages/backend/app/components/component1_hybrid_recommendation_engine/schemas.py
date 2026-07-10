from __future__ import annotations

from pydantic import BaseModel, Field


class RecommendRequest(BaseModel):
    query: str
    user_id: int
    top_k: int = Field(default=20, ge=1, le=100)
    min_rating: float = Field(default=0.0, ge=0, le=5)
    max_price: float | None = Field(default=None, ge=0)
    location: str | None = None


class RecommendBatchRequest(BaseModel):
    user_id: int
    queries: list[str]
    top_k: int = Field(default=10, ge=1, le=100)


class RecommendationScores(BaseModel):
    hybrid: float
    tfidf: float
    bert: float
    cf: float


class RecommendationEngagement(BaseModel):
    interaction_count: int
    booking_success_rate: float


class RecommendationItem(BaseModel):
    rank: int
    provider_id: str
    provider_name: str
    service: str
    location: str
    rating: float
    price: float
    experience_years: int
    scores: RecommendationScores
    engagement: RecommendationEngagement


class RecommendResponse(BaseModel):
    status: str
    query: str
    user_id: str
    timestamp: str
    total_results: int
    recommendations: list[RecommendationItem]
    weights_used: dict[str, float]


class BatchResult(BaseModel):
    query: str
    result: dict


class RecommendBatchResponse(BaseModel):
    status: str
    user_id: int
    batch_size: int
    timestamp: str
    results: list[BatchResult]
