from __future__ import annotations

from datetime import datetime
from fastapi import APIRouter, HTTPException, Query

from .schemas import (
    RecommendBatchRequest,
    RecommendBatchResponse,
    RecommendRequest,
    RecommendResponse,
)
from .service import get_recommender_service

router = APIRouter(prefix="/component1", tags=["component1"])


@router.get("/health")
async def health_check() -> dict:
    return {
        "status": "healthy",
        "service": "hybrid-recommender",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
    }


@router.get("/status")
async def status() -> dict:
    service = get_recommender_service()
    total_providers = 0
    if service.is_loaded:
        artifacts = service._require_artifacts()
        total_providers = len(artifacts.provider_df)

    return {
        "status": "ready",
        "recommender_loaded": service.is_loaded,
        "total_providers": total_providers,
        "weights": service.weights,
        "timestamp": datetime.now().isoformat(),
    }


@router.post("/recommend", response_model=RecommendResponse)
async def recommend(payload: RecommendRequest) -> dict:
    service = get_recommender_service()
    try:
        return service.recommend(
            query=payload.query,
            user_id=payload.user_id,
            top_k=payload.top_k,
            min_rating=payload.min_rating,
            max_price=payload.max_price,
            location=payload.location,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/recommend/batch", response_model=RecommendBatchResponse)
async def recommend_batch(payload: RecommendBatchRequest) -> dict:
    service = get_recommender_service()
    if not payload.queries:
        raise HTTPException(status_code=400, detail="queries must be a non-empty list")
    if len(payload.queries) > 20:
        raise HTTPException(status_code=400, detail="Maximum 20 queries allowed per batch")

    results = []
    for query in payload.queries:
        result = service.recommend(
            query=query.strip(),
            user_id=payload.user_id,
            top_k=payload.top_k,
        )
        results.append({"query": query, "result": result})

    return {
        "status": "success",
        "user_id": payload.user_id,
        "batch_size": len(results),
        "timestamp": datetime.now().isoformat(),
        "results": results,
    }


@router.get("/provider/{provider_id}")
async def get_provider_details(provider_id: int) -> dict:
    service = get_recommender_service()
    artifacts = service._require_artifacts()

    provider_df = artifacts.provider_df
    provider = provider_df[provider_df["provider_id"] == provider_id]
    if provider.empty:
        raise HTTPException(status_code=404, detail=f"Provider {provider_id} not found")

    return {"status": "success", "provider": provider.iloc[0].to_dict()}


@router.get("/providers/search")
async def search_providers(q: str = Query(..., min_length=1), limit: int = Query(10, ge=1, le=100)) -> dict:
    service = get_recommender_service()
    artifacts = service._require_artifacts()
    provider_df = artifacts.provider_df

    query = q.lower()
    mask = (
        provider_df["provider_name"].str.lower().str.contains(query, na=False)
        | provider_df["service"].str.lower().str.contains(query, na=False)
    )
    results = provider_df[mask].head(limit)

    return {
        "status": "success",
        "query": query,
        "count": len(results),
        "providers": results[["provider_id", "provider_name", "service", "rating", "price_lkr"]]
        .fillna("")
        .to_dict("records"),
    }
