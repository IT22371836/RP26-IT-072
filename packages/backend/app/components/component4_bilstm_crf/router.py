from __future__ import annotations

from datetime import datetime
from fastapi import APIRouter, HTTPException

from .schemas import (
    AnalyzeRequest,
    AnalyzeBatchRequest,
    AnalyzeResponse,
    AnalyzeBatchResponse,
    BatchResultItem,
    AspectScores,
    TokenTag,
    ReviewCredibilityRequest,
    ReviewCredibilityResponse,
    LinguisticFeatures,
    ProviderCredibilityResponse,
    RankProvidersRequest,
    RankProvidersResponse,
    ProviderRankEntry,
    PipelineRunRequest,
    PipelineRunResponse,
)
from .service import get_bilstm_crf_service
from .fraud_service import get_fraud_detection_service, extract_linguistic_features
from .credibility_service import get_credibility_service

router = APIRouter(prefix="/component4", tags=["component4"])

_TF_UNAVAILABLE = (
    "Component 4 ALSA is unavailable in this Python environment. "
    "The backend can run without TensorFlow."
)


# ─── Health & Status ──────────────────────────────────────────────────────────

@router.get("/health")
async def health_check() -> dict:
    return {
        "status": "healthy",
        "service": "component4-alsa-fraud-credibility",
        "timestamp": datetime.now().isoformat(),
        "version": "2.0.0",
    }


@router.get("/status")
async def status() -> dict:
    alsa_service = get_bilstm_crf_service()
    fraud_service = get_fraud_detection_service()
    cred_service = get_credibility_service()

    alsa_info: dict = {}
    if alsa_service.is_loaded:
        artifacts = alsa_service._require_artifacts()
        alsa_info = {
            "vocab_size": artifacts.model_config.get("vocab_size"),
            "max_len": artifacts.max_len,
            "num_tags": artifacts.model_config.get("num_tags"),
            "macro_f1": artifacts.model_config.get("macro_f1"),
            "aspect_f1": artifacts.model_config.get("aspect_f1"),
        }

    return {
        "status": "ready",
        "alsa_loaded": alsa_service.is_loaded,
        "fraud_model_loaded": fraud_service.is_loaded,
        "credibility_loaded": cred_service.is_loaded,
        "total_provider_scores": cred_service.total_providers if cred_service.is_loaded else 0,
        "alsa_model_info": alsa_info,
        "timestamp": datetime.now().isoformat(),
    }


# ─── ALSA (Aspect Analysis) ───────────────────────────────────────────────────

@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(payload: AnalyzeRequest) -> dict:
    service = get_bilstm_crf_service()
    try:
        result = service.analyze(payload.text)
    except ImportError as exc:
        raise HTTPException(status_code=503, detail=_TF_UNAVAILABLE) from exc
    except (ValueError, FileNotFoundError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "status": "success",
        "text": payload.text,
        "tokens": result["tokens"],
        "aspects": result["aspects"],
        "timestamp": datetime.now().isoformat(),
    }


@router.post("/analyze/batch", response_model=AnalyzeBatchResponse)
async def analyze_batch(payload: AnalyzeBatchRequest) -> dict:
    if not payload.texts:
        raise HTTPException(status_code=400, detail="texts must be a non-empty list")
    if len(payload.texts) > 20:
        raise HTTPException(status_code=400, detail="Maximum 20 texts allowed per batch")

    service = get_bilstm_crf_service()
    results = []
    for text in payload.texts:
        try:
            result = service.analyze(text)
        except ImportError as exc:
            raise HTTPException(status_code=503, detail=_TF_UNAVAILABLE) from exc
        except (ValueError, FileNotFoundError, RuntimeError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        results.append(
            BatchResultItem(
                text=text,
                result=AnalyzeResponse(
                    status="success",
                    text=text,
                    tokens=[TokenTag(**t) for t in result["tokens"]],
                    aspects=AspectScores(**result["aspects"]),
                    timestamp=datetime.now().isoformat(),
                ),
            )
        )

    return {
        "status": "success",
        "batch_size": len(results),
        "timestamp": datetime.now().isoformat(),
        "results": results,
    }


# ─── Review Credibility (ALSA + Fraud) ───────────────────────────────────────

@router.post("/review/credibility", response_model=ReviewCredibilityResponse)
async def review_credibility(payload: ReviewCredibilityRequest) -> dict:
    """Analyze a review for aspects (ALSA) and fraud risk (Isolation Forest)."""
    alsa_service = get_bilstm_crf_service()
    fraud_service = get_fraud_detection_service()

    try:
        alsa_result = alsa_service.analyze(payload.text)
    except ImportError:
        # Allow demo usage without TensorFlow by returning neutral aspect scores.
        alsa_result = {
            "tokens": [],
            "aspects": {"QUAL": 0.5, "PRICE": 0.5, "TIME": 0.5, "COMM": 0.5},
        }
    except (FileNotFoundError, RuntimeError):
        # If model artifacts are missing, continue with fraud scoring only.
        alsa_result = {
            "tokens": [],
            "aspects": {"QUAL": 0.5, "PRICE": 0.5, "TIME": 0.5, "COMM": 0.5},
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    b = payload.behavioral
    try:
        fraud_result = fraud_service.score_review(
            text=payload.text,
            rating=b.rating if b else None,
            user_total_reviews=b.user_total_reviews if b else 5,
            days_since_prev_review=b.days_since_prev_review if b else 30.0,
            user_provider_diversity=b.user_provider_diversity if b else 3.0,
            text_frequency=b.text_frequency if b else 1,
            days_since_review=b.days_since_review if b else 30.0,
            booking_status=b.booking_status if b else 1,
        )
    except (FileNotFoundError, RuntimeError):
        # If the fraud model isn't available, return a neutral fraud verdict so the demo page can function.
        ling = extract_linguistic_features(payload.text, b.rating if b else None)
        fraud_result = {
            "fraud_score": 0.5,
            "trust_label": "Unverified",
            "is_suspicious": False,
            "linguistic_features": ling,
        }

    return {
        "status": "success",
        "text": payload.text,
        "tokens": alsa_result["tokens"],
        "aspects": alsa_result["aspects"],
        "fraud_score": fraud_result["fraud_score"],
        "trust_label": fraud_result["trust_label"],
        "is_suspicious": fraud_result["is_suspicious"],
        "linguistic_features": fraud_result["linguistic_features"],
        "timestamp": datetime.now().isoformat(),
    }


# ─── Provider Credibility ─────────────────────────────────────────────────────

@router.get("/provider/{provider_id}/credibility", response_model=ProviderCredibilityResponse)
async def provider_credibility(provider_id: str) -> dict:
    """Return pre-computed S_final score and tier for a provider."""
    service = get_credibility_service()
    try:
        result = service.get_provider_credibility(provider_id)
    except (FileNotFoundError, RuntimeError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if result is None:
        raise HTTPException(
            status_code=404, detail=f"Provider '{provider_id}' not found in credibility index"
        )
    return result


@router.post("/providers/rank", response_model=RankProvidersResponse)
async def rank_providers(payload: RankProvidersRequest) -> dict:
    """Rank a list of providers by their S_final credibility score."""
    service = get_credibility_service()
    try:
        ranked = service.rank_providers(payload.provider_ids)
    except (FileNotFoundError, RuntimeError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return {
        "status": "success",
        "total": len(ranked),
        "ranked": ranked,
        "timestamp": datetime.now().isoformat(),
    }


# ─── Component 3 → 4 Pipeline ─────────────────────────────────────────────────

@router.get("/pipeline/run", response_model=PipelineRunResponse)
async def pipeline_run_random() -> dict:
    """
    Run the Component 3 → 4 pipeline with randomly sampled providers.
    Used when Component 3 is not yet integrated.
    """
    service = get_credibility_service()
    try:
        result = service.run_pipeline(provider_ids=None, top_n=5)
    except (FileNotFoundError, RuntimeError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return {
        "status": "success",
        **result,
        "timestamp": datetime.now().isoformat(),
    }


@router.post("/pipeline/run", response_model=PipelineRunResponse)
async def pipeline_run(payload: PipelineRunRequest) -> dict:
    """
    Run the Component 3 → 4 pipeline with explicit provider IDs (from Component 3)
    or randomly if provider_ids is omitted / empty.
    """
    service = get_credibility_service()
    try:
        result = service.run_pipeline(
            provider_ids=payload.provider_ids or None,
            top_n=payload.top_n,
        )
    except (FileNotFoundError, RuntimeError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return {
        "status": "success",
        **result,
        "timestamp": datetime.now().isoformat(),
    }
