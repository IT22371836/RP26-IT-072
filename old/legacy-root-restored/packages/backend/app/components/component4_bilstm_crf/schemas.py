from __future__ import annotations

from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    text: str = Field(..., min_length=1)


class AnalyzeBatchRequest(BaseModel):
    texts: list[str] = Field(..., min_length=1)


class TokenTag(BaseModel):
    token: str
    tag: str


class AspectScores(BaseModel):
    QUAL: float | None = None
    PRICE: float | None = None
    TIME: float | None = None
    COMM: float | None = None


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
