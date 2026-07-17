from pydantic import BaseModel, Field, field_validator


class RecommendationRequest(BaseModel):
    query: str = Field(min_length=3, max_length=2000)
    category: str | None = Field(default=None, min_length=2, max_length=100)
    district: str | None = Field(default=None, min_length=2, max_length=100)
    city: str | None = Field(default=None, min_length=2, max_length=100)
    min_rating: float = Field(default=0.0, ge=0, le=5)
    top_k: int = Field(default=20, ge=1, le=20)

    @field_validator("query")
    @classmethod
    def normalize_query(cls, value: str) -> str:
        return " ".join(value.split())


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


class RecommendationResponse(BaseModel):
    component_version: str
    model_version: str
    query: str
    user_id: str
    results: list[ProviderRecommendation]


class ComponentStatusResponse(BaseModel):
    ready: bool
    component_version: str | None = None
    model_version: str | None = None
    provider_count: int | None = None
    detail: str | None = None
