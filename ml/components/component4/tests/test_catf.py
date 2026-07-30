from __future__ import annotations

import json
import hashlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


COMPONENT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = COMPONENT_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from catf_ranking import CATFRanker, CATFRankingError  # noqa: E402
from catf_service import (  # noqa: E402
    ASPECTS,
    ReviewPrediction,
    calculate_provider_score,
    load_catf_config,
    load_weight_profiles,
    prediction_confidence,
    signed_sentiment,
)


ARTIFACT_DIR = COMPONENT_ROOT / "artifacts" / "catf-v1"
PROVIDER_SCORES = ARTIFACT_DIR / "provider_catf_scores.csv"
MANIFEST = ARTIFACT_DIR / "manifest.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def test_signed_sentiment_and_confidence_follow_pdf_equations() -> None:
    probabilities = [0.7, 0.2, 0.1]
    assert signed_sentiment(probabilities) == pytest.approx(0.6)
    assert prediction_confidence(probabilities) == pytest.approx(0.7)


def test_all_component1_categories_have_valid_weight_profiles() -> None:
    profiles = load_weight_profiles()
    providers_path = (
        COMPONENT_ROOT.parents[2]
        / "packages"
        / "backend"
        / "app"
        / "components"
        / "component1"
        / "artifacts"
        / "providers.json"
    )
    providers = json.loads(providers_path.read_text(encoding="utf-8"))
    provider_categories = {provider["category"] for provider in providers}

    assert provider_categories == set(profiles["categories"])
    for weights in profiles["categories"].values():
        assert set(weights) == set(ASPECTS)
        assert sum(weights.values()) == pytest.approx(1.0)


def test_credibility_reduces_a_reviews_influence() -> None:
    config = load_catf_config()
    equal_weights = {aspect: 0.25 for aspect in ASPECTS}
    positive = {aspect: [0.9, 0.05, 0.05] for aspect in ASPECTS}
    negative = {aspect: [0.05, 0.05, 0.9] for aspect in ASPECTS}
    result = calculate_provider_score(
        [
            ReviewPrediction(probabilities=positive, credibility=0.1),
            ReviewPrediction(probabilities=negative, credibility=1.0),
        ],
        equal_weights,
        category_prior=0.5,
        config=config,
    )

    assert all(value < 0 for value in result["aspect_scores"].values())
    assert result["effective_review_count"] == pytest.approx(1.1)


def test_no_review_provider_uses_category_prior_and_zero_reliability() -> None:
    result = calculate_provider_score(
        [],
        {aspect: 0.25 for aspect in ASPECTS},
        category_prior=0.46,
        config=load_catf_config(),
    )

    assert result["final_catf_score"] == pytest.approx(0.46)
    assert result["reliability_factor"] == 0
    assert result["score_source"] == "category_prior"
    assert result["evidence_status"] == "insufficient"


def test_full_provider_artifact_is_complete_bounded_and_uses_fallbacks() -> None:
    scores = pd.read_csv(PROVIDER_SCORES)

    assert len(scores) == 10_000
    assert scores["provider_id"].nunique() == 10_000
    assert scores["review_count"].gt(0).sum() == 4_976
    assert scores["review_count"].eq(0).sum() == 5_024
    assert scores["final_catf_score"].between(0, 1).all()
    assert np.isfinite(
        scores.select_dtypes(include=[np.number]).to_numpy(dtype=np.float64)
    ).all()
    fallback = scores[scores["review_count"].eq(0)]
    np.testing.assert_allclose(
        fallback["final_catf_score"],
        fallback["category_prior"],
    )
    assert set(fallback["score_source"]) == {"category_prior"}


def test_manifest_hashes_every_input_artifact_and_report() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    repository_root = COMPONENT_ROOT.parents[2]

    checked = 0
    for section in ("inputs", "artifacts", "reports"):
        for metadata in manifest[section].values():
            path = repository_root / metadata["path"]
            assert path.is_file()
            assert path.stat().st_size == metadata["bytes"]
            assert sha256_file(path) == metadata["sha256"]
            checked += 1

    assert checked == 15


def test_top10_to_top5_is_deterministic_and_never_adds_candidates() -> None:
    scores = pd.read_csv(PROVIDER_SCORES)
    candidates = scores["provider_id"].head(10).tolist()
    ranker = CATFRanker(PROVIDER_SCORES, MANIFEST)

    first = ranker.rank(candidates, request_id="same-request", top_k=5)
    second = ranker.rank(list(reversed(candidates)), request_id="same-request", top_k=5)

    assert first["input_count"] == 10
    assert first["output_count"] == 5
    assert first["run_id"] == second["run_id"]
    assert first["providers"] == second["providers"]
    assert {row["provider_id"] for row in first["providers"]}.issubset(candidates)


def test_ranker_returns_all_candidates_when_fewer_than_five_are_available() -> None:
    scores = pd.read_csv(PROVIDER_SCORES)
    candidates = scores["provider_id"].head(3).tolist()
    result = CATFRanker(PROVIDER_SCORES, MANIFEST).rank(
        candidates,
        request_id="three-candidates",
        top_k=5,
    )

    assert result["input_count"] == 3
    assert result["output_count"] == 3


def test_ranker_rejects_duplicate_and_unknown_provider_ids() -> None:
    ranker = CATFRanker(PROVIDER_SCORES, MANIFEST)
    known = pd.read_csv(PROVIDER_SCORES, nrows=1)["provider_id"].iloc[0]

    with pytest.raises(CATFRankingError, match="unique"):
        ranker.rank([known, known], request_id="duplicates")
    with pytest.raises(CATFRankingError, match="unknown"):
        ranker.rank(["P-NOT-REAL"], request_id="unknown")


def test_tie_break_order_is_effective_count_credibility_then_provider_id(
    tmp_path: Path,
) -> None:
    rows = []
    tie_data = [
        ("P00003", 0.5, 2.0, 0.8),
        ("P00002", 0.5, 3.0, 0.7),
        ("P00001", 0.5, 3.0, 0.7),
    ]
    for provider_id, score, effective, credibility in tie_data:
        row = {
            "provider_id": provider_id,
            "provider_name": provider_id,
            "category": "Plumbers",
            "district": "Colombo",
            "final_catf_score": score,
            "effective_review_count": effective,
            "mean_credibility": credibility,
            "reliability_factor": 0.1,
            "review_count": 4,
            "evidence_status": "insufficient",
            "score_source": "catf_evidence",
        }
        row.update({f"{aspect}_score": 0.0 for aspect in ASPECTS})
        rows.append(row)
    scores_path = tmp_path / "scores.csv"
    manifest_path = tmp_path / "manifest.json"
    pd.DataFrame(rows).to_csv(scores_path, index=False)
    manifest_path.write_text(
        json.dumps(
            {
                "catf_version": "catf-v1",
                "weight_version": "category-weights-v1",
                "category_prior_version": "category-priors-v1",
                "absa_model_version": "absa-v1",
                "credibility_model_version": "credibility-v1",
            }
        ),
        encoding="utf-8",
    )

    result = CATFRanker(scores_path, manifest_path).rank(
        ["P00003", "P00002", "P00001"],
        request_id="ties",
        top_k=3,
    )

    assert [row["provider_id"] for row in result["providers"]] == [
        "P00001",
        "P00002",
        "P00003",
    ]
