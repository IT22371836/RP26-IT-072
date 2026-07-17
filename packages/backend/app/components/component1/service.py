from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

from app.components.component1.schemas import ProviderRecommendation


class ArtifactsUnavailableError(Exception):
    pass


class ArtifactValidationError(Exception):
    pass


class HybridRecommendationEngine:
    def __init__(self, artifact_dir: Path) -> None:
        self.artifact_dir = artifact_dir
        self.ready = False
        self.manifest: dict[str, Any] = {}
        self.providers: list[dict[str, Any]] = []
        self.vectorizer: Any = None
        self.tfidf_matrix: Any = None
        self.provider_embeddings: np.ndarray | None = None
        self.credibility_scores: np.ndarray | None = None
        self.user_preferences: dict[str, list[str]] = {}
        self.semantic_model: Any = None
        self._provider_index: dict[str, int] = {}

    @staticmethod
    def normalize(scores: np.ndarray) -> np.ndarray:
        scores = np.nan_to_num(np.asarray(scores, dtype=np.float32), nan=0.0)
        minimum = float(scores.min())
        maximum = float(scores.max())
        if maximum == minimum:
            return np.full_like(scores, 0.5)
        return (scores - minimum) / (maximum - minimum)

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as file:
            for chunk in iter(lambda: file.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def load(self) -> None:
        manifest_path = self.artifact_dir / "manifest.json"
        if not manifest_path.exists():
            raise ArtifactsUnavailableError(
                f"Component 1 manifest is missing from {self.artifact_dir}"
            )

        import joblib
        from scipy import sparse
        from sentence_transformers import SentenceTransformer

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("schema_version") != 1:
            raise ArtifactValidationError("Unsupported Component 1 artifact schema")
        for name, expected in manifest.get("checksums", {}).items():
            path = self.artifact_dir / name
            if not path.exists() or self._sha256(path) != expected:
                raise ArtifactValidationError(f"Artifact checksum failed: {name}")

        providers = json.loads((self.artifact_dir / "providers.json").read_text("utf-8"))
        tfidf_matrix = sparse.load_npz(self.artifact_dir / "tfidf_matrix.npz")
        embeddings = np.load(self.artifact_dir / "provider_embeddings.npy")
        credibility = np.load(self.artifact_dir / "credibility_scores.npy")
        expected_count = int(manifest["provider_count"])
        if not (
            len(providers)
            == tfidf_matrix.shape[0]
            == embeddings.shape[0]
            == credibility.shape[0]
            == expected_count
        ):
            raise ArtifactValidationError("Component 1 artifact row counts do not match")

        self.manifest = manifest
        self.providers = providers
        self.vectorizer = joblib.load(self.artifact_dir / "tfidf_vectorizer.joblib")
        self.tfidf_matrix = tfidf_matrix
        self.provider_embeddings = embeddings
        self.credibility_scores = credibility
        self.user_preferences = json.loads(
            (self.artifact_dir / "user_preferences.json").read_text("utf-8")
        )
        self.semantic_model = SentenceTransformer(str(self.artifact_dir / "semantic_model"))
        self._provider_index = {
            provider["provider_id"]: index for index, provider in enumerate(providers)
        }
        self.ready = True

    def status(self) -> dict[str, Any]:
        if not self.ready:
            return {"ready": False, "detail": "Component 1 artifacts are not loaded"}
        return {
            "ready": True,
            "component_version": self.manifest["component_version"],
            "model_version": self.manifest["model_version"],
            "provider_count": len(self.providers),
        }

    def _cf_scores(self, user_id: str) -> np.ndarray:
        if self.credibility_scores is None:
            raise ArtifactsUnavailableError("Component 1 artifacts are not loaded")
        scores = self.credibility_scores.astype(np.float32).copy()
        for provider_id, count in Counter(self.user_preferences.get(user_id, [])).items():
            if (index := self._provider_index.get(provider_id)) is not None:
                scores[index] *= 1.2**count
        return np.clip(np.nan_to_num(scores, nan=0.5), 0, 1)

    def recommend(
        self,
        query: str,
        user_id: str,
        top_k: int = 20,
        category: str | None = None,
        district: str | None = None,
        city: str | None = None,
        min_rating: float = 0.0,
    ) -> list[ProviderRecommendation]:
        if not self.ready or self.provider_embeddings is None:
            raise ArtifactsUnavailableError("Component 1 artifacts are not loaded")

        query_vector = self.vectorizer.transform([query.lower().strip()])
        tfidf_raw = (self.tfidf_matrix @ query_vector.T).toarray().ravel()
        query_embedding = self.semantic_model.encode(
            [query.lower().strip()],
            convert_to_numpy=True,
            normalize_embeddings=True,
        )[0]
        bert_raw = self.provider_embeddings @ query_embedding
        cf_raw = self._cf_scores(user_id)

        tfidf = self.normalize(tfidf_raw)
        bert = self.normalize(bert_raw)
        cf = self.normalize(cf_raw)
        weights = self.manifest["weights"]
        hybrid = np.clip(
            weights["tfidf"] * tfidf + weights["bert"] * bert + weights["cf"] * cf,
            0,
            1,
        )

        candidates: list[int] = []
        for index, provider in enumerate(self.providers):
            if category and provider["category"].lower() != category.lower():
                continue
            if district and provider["district"].lower() != district.lower():
                continue
            if city and provider["city"].lower() != city.lower():
                continue
            if float(provider["rating"]) < min_rating:
                continue
            candidates.append(index)
        candidates.sort(key=lambda index: float(hybrid[index]), reverse=True)

        results = []
        for index in candidates[:top_k]:
            results.append(
                ProviderRecommendation(
                    **self.providers[index],
                    hybrid_score=float(hybrid[index]),
                    tfidf_score=float(tfidf[index]),
                    bert_score=float(bert[index]),
                    cf_score=float(cf[index]),
                )
            )
        return results


_engine: HybridRecommendationEngine | None = None


def get_recommendation_engine(artifact_dir: Path) -> HybridRecommendationEngine:
    global _engine
    if _engine is None or _engine.artifact_dir != artifact_dir:
        _engine = HybridRecommendationEngine(artifact_dir)
        try:
            _engine.load()
        except ArtifactsUnavailableError:
            pass
    return _engine
