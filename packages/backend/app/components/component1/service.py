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
    CATEGORY_ALIASES = {
        "electrician": "electricians",
        "plumber": "plumbers",
        "ac repair": "a/c",
        "air conditioning": "a/c",
        "carpenter": "carpenters",
        "painter": "painters",
    }

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

        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ArtifactValidationError("Component 1 manifest is not valid JSON") from error
        if manifest.get("schema_version") != 1:
            raise ArtifactValidationError("Unsupported Component 1 artifact schema")

        required_files = {
            "providers.json",
            "tfidf_vectorizer.joblib",
            "tfidf_matrix.npz",
            "provider_embeddings.npy",
            "credibility_scores.npy",
            "user_preferences.json",
            "semantic_model/config.json",
        }
        checksums = manifest.get("checksums")
        if not isinstance(checksums, dict) or not required_files.issubset(checksums):
            raise ArtifactValidationError("Component 1 manifest has incomplete checksums")
        for name, expected in checksums.items():
            if not isinstance(name, str) or not isinstance(expected, str):
                raise ArtifactValidationError("Component 1 manifest has invalid checksums")
            path = self.artifact_dir / name
            if not path.exists() or self._sha256(path) != expected:
                raise ArtifactValidationError(f"Artifact checksum failed: {name}")

        weights = manifest.get("weights")
        if (
            not isinstance(weights, dict)
            or set(weights) != {"tfidf", "bert", "cf"}
            or any(not isinstance(value, (int, float)) or value < 0 for value in weights.values())
            or not np.isclose(sum(weights.values()), 1.0)
        ):
            raise ArtifactValidationError("Component 1 manifest has invalid hybrid weights")

        try:
            providers = json.loads((self.artifact_dir / "providers.json").read_text("utf-8"))
            tfidf_matrix = sparse.load_npz(self.artifact_dir / "tfidf_matrix.npz")
            embeddings = np.load(self.artifact_dir / "provider_embeddings.npy")
            credibility = np.load(self.artifact_dir / "credibility_scores.npy")
            expected_count = int(manifest["provider_count"])
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
            raise ArtifactValidationError("Component 1 artifacts could not be decoded") from error
        if not (
            len(providers)
            == tfidf_matrix.shape[0]
            == embeddings.shape[0]
            == credibility.shape[0]
            == expected_count
        ):
            raise ArtifactValidationError("Component 1 artifact row counts do not match")
        required_provider_fields = set(ProviderRecommendation.model_fields) - {
            "hybrid_score",
            "tfidf_score",
            "bert_score",
            "cf_score",
        }
        if not isinstance(providers, list) or any(
            not isinstance(provider, dict) or not required_provider_fields.issubset(provider)
            for provider in providers
        ):
            raise ArtifactValidationError("Component 1 provider records are invalid")
        provider_ids = [provider["provider_id"] for provider in providers]
        if len(set(provider_ids)) != len(provider_ids):
            raise ArtifactValidationError("Component 1 provider IDs are not unique")
        if embeddings.ndim != 2 or embeddings.shape[1] != manifest.get("embedding_dimension"):
            raise ArtifactValidationError("Component 1 embedding dimensions do not match")
        if credibility.ndim != 1 or not np.isfinite(credibility).all():
            raise ArtifactValidationError("Component 1 credibility scores are invalid")
        if not sparse.isspmatrix(tfidf_matrix) or not np.isfinite(tfidf_matrix.data).all():
            raise ArtifactValidationError("Component 1 TF-IDF matrix is invalid")

        try:
            vectorizer = joblib.load(self.artifact_dir / "tfidf_vectorizer.joblib")
            self.user_preferences = json.loads(
                (self.artifact_dir / "user_preferences.json").read_text("utf-8")
            )
            semantic_model = SentenceTransformer(str(self.artifact_dir / "semantic_model"))
        except Exception as error:
            raise ArtifactValidationError("Component 1 model state could not be loaded") from error
        if not isinstance(self.user_preferences, dict):
            raise ArtifactValidationError("Component 1 user preferences are invalid")

        self.manifest = manifest
        self.providers = providers
        self.vectorizer = vectorizer
        self.tfidf_matrix = tfidf_matrix
        self.provider_embeddings = embeddings
        self.credibility_scores = credibility
        self.semantic_model = semantic_model
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

    def _cf_scores(
        self, user_id: str, additional_preferences: list[str] | None = None
    ) -> np.ndarray:
        if self.credibility_scores is None:
            raise ArtifactsUnavailableError("Component 1 artifacts are not loaded")
        scores = self.credibility_scores.astype(np.float32).copy()
        preferences = [
            *self.user_preferences.get(user_id, []),
            *(additional_preferences or []),
        ]
        for provider_id, count in Counter(preferences).items():
            if (index := self._provider_index.get(provider_id)) is not None:
                scores[index] *= 1.2**count
        return np.clip(np.nan_to_num(scores, nan=0.5), 0, 1)

    @classmethod
    def _category_key(cls, value: str) -> str:
        normalized = value.lower().strip()
        return cls.CATEGORY_ALIASES.get(normalized, normalized)

    def recommend(
        self,
        query: str,
        user_id: str,
        top_k: int = 20,
        category: str | None = None,
        district: str | None = None,
        city: str | None = None,
        min_rating: float = 0.0,
        additional_providers: list[dict[str, Any]] | None = None,
        additional_preferences: list[str] | None = None,
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
        cf_raw = self._cf_scores(user_id, additional_preferences)

        providers = list(self.providers)
        known_provider_ids = {provider["provider_id"] for provider in providers}
        live_providers = [
            provider
            for provider in (additional_providers or [])
            if provider.get("provider_id") not in known_provider_ids
        ]
        if live_providers:
            live_text = [
                " ".join(
                    (
                        str(provider.get("category", "")),
                        " ".join(provider.get("skills", [])),
                        str(provider.get("description", "")),
                    )
                ).lower()
                for provider in live_providers
            ]
            live_tfidf_matrix = self.vectorizer.transform(live_text)
            live_tfidf = (live_tfidf_matrix @ query_vector.T).toarray().ravel()
            live_embeddings = self.semantic_model.encode(
                live_text,
                convert_to_numpy=True,
                normalize_embeddings=True,
            )
            live_bert = live_embeddings @ query_embedding
            live_cf = np.array(
                [
                    0.5
                    if int(provider.get("interaction_count", 0)) == 0
                    else (
                        float(provider.get("rating", 0)) / 5.0 * 0.50
                        + float(provider.get("booking_success_rate", 0)) * 0.30
                        + np.tanh(float(provider.get("interaction_count", 0)) / 100.0) * 0.20
                    )
                    for provider in live_providers
                ],
                dtype=np.float32,
            )
            tfidf_raw = np.concatenate((tfidf_raw, live_tfidf))
            bert_raw = np.concatenate((bert_raw, live_bert))
            cf_raw = np.concatenate((cf_raw, live_cf))
            providers.extend(
                {
                    **provider,
                    "skills": ", ".join(provider.get("skills", [])),
                }
                for provider in live_providers
            )

        tfidf = self.normalize(tfidf_raw)
        bert = self.normalize(bert_raw)
        cf = self.normalize(cf_raw)
        weights = self.manifest["weights"]
        hybrid = np.clip(
            weights["tfidf"] * tfidf + weights["bert"] * bert + weights["cf"] * cf,
            0,
            1,
        )

        category_key = self._category_key(category) if category else None
        district_key = district.lower().strip() if district else None
        city_key = city.lower().strip() if city else None
        eligible = [
            index
            for index, provider in enumerate(providers)
            if float(provider["rating"]) >= min_rating
        ]

        def matches(index: int, *, use_category: bool, use_district: bool, use_city: bool) -> bool:
            provider = providers[index]
            return (
                (
                    not use_category
                    or not category_key
                    or self._category_key(provider["category"]) == category_key
                )
                and (
                    not use_district
                    or not district_key
                    or provider["district"].lower() == district_key
                )
                and (not use_city or not city_key or provider["city"].lower() == city_key)
            )

        candidates: list[int] = []
        selected: set[int] = set()
        for use_category, use_district, use_city in (
            (True, True, True),
            (True, True, False),
            (True, False, False),
            (False, False, False),
        ):
            tier = [
                index
                for index in eligible
                if index not in selected
                and matches(
                    index,
                    use_category=use_category,
                    use_district=use_district,
                    use_city=use_city,
                )
            ]
            tier.sort(key=lambda index: float(hybrid[index]), reverse=True)
            candidates.extend(tier[: top_k - len(candidates)])
            selected.update(tier)
            if len(candidates) == top_k:
                break

        results = []
        for index in candidates[:top_k]:
            results.append(
                ProviderRecommendation(
                    **providers[index],
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
    if not _engine.ready:
        try:
            _engine.load()
        except (ArtifactsUnavailableError, ArtifactValidationError):
            pass
    return _engine
