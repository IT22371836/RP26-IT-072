from pathlib import Path

import numpy as np
from scipy import sparse
from sklearn.feature_extraction.text import TfidfVectorizer

from app.components.component1.service import (
    ArtifactsUnavailableError,
    ArtifactValidationError,
    HybridRecommendationEngine,
)


class FakeSemanticModel:
    def encode(self, texts, **_kwargs) -> np.ndarray:
        return np.array([[1.0, 0.0] for _ in texts], dtype=np.float32)


def build_engine() -> HybridRecommendationEngine:
    engine = HybridRecommendationEngine(Path("unused"))
    engine.providers = [
        {
            "provider_id": "P001",
            "provider_name": "Colombo Electric",
            "category": "Electrician",
            "district": "Colombo",
            "city": "Colombo",
            "skills": "wiring repair",
            "description": "Electrical wiring specialist",
            "experience_years": 8,
            "rating": 4.8,
            "review_count": 100,
            "booking_success_rate": 0.95,
            "interaction_count": 120,
        },
        {
            "provider_id": "P002",
            "provider_name": "Galle Plumbing",
            "category": "Plumber",
            "district": "Galle",
            "city": "Galle",
            "skills": "pipe repair",
            "description": "Water pipe specialist",
            "experience_years": 5,
            "rating": 4.2,
            "review_count": 50,
            "booking_success_rate": 0.8,
            "interaction_count": 70,
        },
    ]
    engine.vectorizer = TfidfVectorizer().fit(
        ["electrician wiring repair", "plumber water pipe repair"]
    )
    engine.tfidf_matrix = sparse.csr_matrix(
        engine.vectorizer.transform(["electrician wiring repair", "plumber water pipe repair"])
    )
    engine.provider_embeddings = np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)
    engine.credibility_scores = np.array([0.9, 0.5], dtype=np.float32)
    engine.semantic_model = FakeSemanticModel()
    engine.user_preferences = {"U001": ["P001"]}
    engine._provider_index = {"P001": 0, "P002": 1}
    engine.manifest = {
        "component_version": "test",
        "model_version": "test",
        "weights": {"tfidf": 0.30, "bert": 0.35, "cf": 0.35},
    }
    engine.ready = True
    return engine


def test_normalize_constant_scores_is_neutral() -> None:
    scores = HybridRecommendationEngine.normalize(np.array([3.0, 3.0]))
    assert scores.tolist() == [0.5, 0.5]


def test_generated_audit_fields_are_not_required_in_static_artifacts() -> None:
    required = HybridRecommendationEngine.required_artifact_provider_fields()

    assert "provider_id" in required
    assert "selection_tier" not in required
    assert "selection_reason" not in required


def test_recommend_ranks_relevant_provider_and_applies_filters() -> None:
    results = build_engine().recommend(
        query="electrician wiring",
        user_id="U001",
        category="Electrician",
        district="Colombo",
        min_rating=4.5,
    )

    assert [result.provider_id for result in results] == ["P001"]
    assert 0 <= results[0].hybrid_score <= 1
    assert results[0].selection_tier == "exact category and district match"
    assert "hybrid score" in results[0].selection_reason
    assert "strongest signal" in results[0].selection_reason


def test_recommend_broadens_location_to_preserve_candidate_handoff() -> None:
    results = build_engine().recommend(
        query="electrician wiring",
        user_id="U001",
        category="Electricians",
        district="Colombo",
        city="Kottawa",
        top_k=2,
    )

    assert results[0].provider_id == "P001"
    assert len(results) == 2


def test_recommend_scores_newly_registered_provider_with_static_pool() -> None:
    firebase_uid = "GsMrbJuYYHR7d0uKEqA5OVjdKV73"
    live_provider = {
        "provider_id": firebase_uid,
        "provider_name": "Kottawa Electrical Care",
        "category": "Electricians",
        "district": "Colombo",
        "city": "Kottawa",
        "skills": ["wiring", "socket repair"],
        "description": "Electrical wiring specialist in Kottawa",
        "experience_years": 4,
        "rating": 0.0,
        "review_count": 0,
        "booking_success_rate": 0.0,
        "interaction_count": 0,
    }

    results = build_engine().recommend(
        query="electrician wiring",
        user_id="U001",
        category="Electricians",
        district="Colombo",
        city="Kottawa",
        top_k=2,
        additional_providers=[live_provider],
    )

    assert firebase_uid in [provider.provider_id for provider in results]


def test_recommend_never_returns_provider_outside_allowed_firebase_pool() -> None:
    results = build_engine().recommend(
        query="electrician wiring",
        user_id="U001",
        top_k=20,
        allowed_provider_ids={"P002"},
    )

    assert [provider.provider_id for provider in results] == ["P002"]


def test_missing_artifacts_fail_explicitly() -> None:
    engine = HybridRecommendationEngine(Path("missing"))

    try:
        engine.recommend("electrician", "U001")
    except ArtifactsUnavailableError as error:
        assert "not loaded" in str(error)
    else:
        raise AssertionError("Missing artifacts must not produce fallback recommendations")


def test_load_rejects_manifest_without_required_checksums(tmp_path: Path) -> None:
    (tmp_path / "manifest.json").write_text(
        '{"schema_version": 1, "checksums": {}}', encoding="utf-8"
    )

    try:
        HybridRecommendationEngine(tmp_path).load()
    except ArtifactValidationError as error:
        assert "incomplete checksums" in str(error)
    else:
        raise AssertionError("Incomplete artifacts must fail manifest validation")


def test_load_rejects_invalid_manifest_json(tmp_path: Path) -> None:
    (tmp_path / "manifest.json").write_text("not-json", encoding="utf-8")

    try:
        HybridRecommendationEngine(tmp_path).load()
    except ArtifactValidationError as error:
        assert "not valid JSON" in str(error)
    else:
        raise AssertionError("Invalid manifest JSON must fail validation")
