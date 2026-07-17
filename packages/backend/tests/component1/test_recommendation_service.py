from pathlib import Path

import numpy as np
from scipy import sparse
from sklearn.feature_extraction.text import TfidfVectorizer

from app.components.component1.service import (
    ArtifactsUnavailableError,
    HybridRecommendationEngine,
)


class FakeSemanticModel:
    def encode(self, *_args, **_kwargs) -> np.ndarray:
        return np.array([[1.0, 0.0]], dtype=np.float32)


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
        engine.vectorizer.transform(
            ["electrician wiring repair", "plumber water pipe repair"]
        )
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


def test_missing_artifacts_fail_explicitly() -> None:
    engine = HybridRecommendationEngine(Path("missing"))

    try:
        engine.recommend("electrician", "U001")
    except ArtifactsUnavailableError as error:
        assert "not loaded" in str(error)
    else:
        raise AssertionError("Missing artifacts must not produce fallback recommendations")
