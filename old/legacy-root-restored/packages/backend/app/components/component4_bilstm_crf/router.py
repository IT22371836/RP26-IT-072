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
)
from .service import get_bilstm_crf_service

router = APIRouter(prefix="/component4", tags=["component4"])


@router.get("/health")
async def health_check() -> dict:
    return {
        "status": "healthy",
        "service": "bilstm-crf-aspect-analyzer",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
    }


@router.get("/status")
async def status() -> dict:
    service = get_bilstm_crf_service()
    cfg = {}
    if service.is_loaded:
        artifacts = service._require_artifacts()
        cfg = {
            "vocab_size": artifacts.model_config.get("vocab_size"),
            "max_len": artifacts.max_len,
            "num_tags": artifacts.model_config.get("num_tags"),
            "macro_f1": artifacts.model_config.get("macro_f1"),
            "aspect_f1": artifacts.model_config.get("aspect_f1"),
        }
    return {
        "status": "ready",
        "model_loaded": service.is_loaded,
        "model_info": cfg,
        "timestamp": datetime.now().isoformat(),
    }


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(payload: AnalyzeRequest) -> dict:
    service = get_bilstm_crf_service()
    try:
        result = service.analyze(payload.text)
    except ImportError as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "Component 4 is unavailable in this Python environment. "
                "The backend can run without TensorFlow."
            ),
        ) from exc
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
            raise HTTPException(
                status_code=503,
                detail=(
                    "Component 4 is unavailable in this Python environment. "
                    "The backend can run without TensorFlow."
                ),
            ) from exc
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
