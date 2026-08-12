from __future__ import annotations

import csv
import hashlib
import json
import math
import time
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.components.component4.schemas import (
    ASPECTS,
    Component4RankRequest,
    Component4RankResponse,
)
from app.repositories.component4 import Component4Repository
from app.schemas.common import utc_now

REPOSITORY_ROOT = Path(__file__).resolve().parents[5]
DEFAULT_EVALUATION_MANIFEST = (
    REPOSITORY_ROOT
    / "ml"
    / "components"
    / "component4"
    / "artifacts"
    / "evaluation-v1"
    / "manifest.json"
)
DEFAULT_RELEASE_REPORT = (
    REPOSITORY_ROOT
    / "ml"
    / "components"
    / "component4"
    / "reports"
    / "release-v1"
    / "release_readiness.json"
)
COMPONENT_VERSION = "component4-phase12"


class ArtifactsUnavailableError(Exception):
    pass


class ArtifactValidationError(Exception):
    pass


class UnknownProviderError(Exception):
    def __init__(self, provider_ids: list[str]) -> None:
        super().__init__(f"Unknown provider IDs: {provider_ids}")
        self.provider_ids = provider_ids


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ArtifactValidationError(message)


def finite_float(value: Any, field: str) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError) as error:
        raise ArtifactValidationError(f"{field} must be numeric") from error
    require(math.isfinite(numeric), f"{field} must be finite")
    return numeric


class Component4RankingEngine:
    """Immutable CATF snapshot with optional Phase 8 evaluation metadata."""

    def __init__(
        self,
        artifact_dir: Path,
        category_priors_path: Path,
        evaluation_manifest_path: Path | None = None,
        release_report_path: Path | None = None,
    ) -> None:
        self.artifact_dir = artifact_dir.resolve()
        self.category_priors_path = category_priors_path.resolve()
        self.evaluation_manifest_path = (
            evaluation_manifest_path or DEFAULT_EVALUATION_MANIFEST
        ).resolve()
        self.release_report_path = (
            release_report_path or DEFAULT_RELEASE_REPORT
        ).resolve()
        self.ready = False
        self.manifest: dict[str, Any] = {}
        self.config: dict[str, Any] = {}
        self.weight_profiles: dict[str, Any] = {}
        self.category_priors: dict[str, Any] = {}
        self.provider_scores: dict[str, dict[str, Any]] = {}
        self.evaluation: dict[str, Any] = {}
        self.release_evidence: dict[str, Any] = {}

    @property
    def versions(self) -> dict[str, str]:
        keys = (
            "catf_version",
            "weight_version",
            "category_prior_version",
            "absa_model_version",
            "credibility_model_version",
        )
        return {key: str(self.manifest[key]) for key in keys}

    def _load_json(self, path: Path, label: str) -> dict[str, Any]:
        if not path.is_file():
            raise ArtifactsUnavailableError(f"Component 4 {label} is missing: {path}")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ArtifactValidationError(f"Component 4 {label} is not valid JSON") from error
        require(isinstance(payload, dict), f"Component 4 {label} must be a JSON object")
        return payload

    def _verify_file(self, path: Path, metadata: Any, label: str) -> None:
        if not path.is_file():
            raise ArtifactsUnavailableError(f"Component 4 {label} is missing: {path}")
        require(isinstance(metadata, dict), f"Manifest metadata is missing for {label}")
        expected_hash = metadata.get("sha256")
        expected_bytes = metadata.get("bytes")
        require(isinstance(expected_hash, str), f"Manifest SHA-256 is missing for {label}")
        require(isinstance(expected_bytes, int), f"Manifest byte count is missing for {label}")
        require(path.stat().st_size == expected_bytes, f"Artifact byte count failed: {label}")
        require(sha256_file(path) == expected_hash, f"Artifact checksum failed: {label}")

    def _load_evaluation(self, phase5_manifest_path: Path) -> dict[str, Any]:
        if not self.evaluation_manifest_path.is_file():
            return {}
        evaluation = self._load_json(
            self.evaluation_manifest_path,
            "Phase 8 evaluation manifest",
        )
        require(
            evaluation.get("evaluation_version") == "ranking-evaluation-v1",
            "Phase 8 evaluation version mismatch",
        )
        require(evaluation.get("status") == "passed", "Phase 8 evaluation did not pass")
        require(
            evaluation.get("validation_scope")
            == "held_out_proxy_not_production_ground_truth",
            "Phase 8 evaluation scope is not explicit",
        )
        inputs = evaluation.get("inputs")
        reports = evaluation.get("reports")
        require(isinstance(inputs, dict), "Phase 8 input metadata is missing")
        require(isinstance(reports, dict), "Phase 8 report metadata is missing")
        self._verify_file(
            phase5_manifest_path,
            inputs.get("phase5_manifest"),
            "Phase 8 Phase 5 manifest input",
        )
        audit_metadata = reports.get("ranking_evaluation")
        require(isinstance(audit_metadata, dict), "Phase 8 audit metadata is missing")
        audit_path = REPOSITORY_ROOT / str(audit_metadata.get("path", ""))
        self._verify_file(audit_path, audit_metadata, "Phase 8 ranking evaluation")
        audit = self._load_json(audit_path, "Phase 8 ranking evaluation")
        require(audit.get("status") == "passed", "Phase 8 ranking evaluation did not pass")
        require(
            audit.get("ranking_ground_truth_validation")
            == evaluation.get("ranking_ground_truth_validation"),
            "Phase 8 validation status mismatch",
        )
        require(
            audit.get("production_ground_truth_validation")
            == evaluation.get("production_ground_truth_validation"),
            "Phase 8 production limitation mismatch",
        )
        return evaluation

    def _load_release_evidence(self, phase5_manifest_path: Path) -> dict[str, Any]:
        if not self.release_report_path.is_file():
            return {}
        release_manifest_path = self.release_report_path.parent / "manifest.json"
        release_manifest = self._load_json(
            release_manifest_path,
            "Phase 10 release manifest",
        )
        require(
            release_manifest.get("release_evidence_version")
            == "component4-release-evidence-v1",
            "Phase 10 release version mismatch",
        )
        require(release_manifest.get("status") == "passed", "Phase 10 release gate failed")
        inputs = release_manifest.get("inputs")
        reports = release_manifest.get("reports")
        require(isinstance(inputs, dict), "Phase 10 input metadata is missing")
        require(isinstance(reports, dict), "Phase 10 report metadata is missing")
        self._verify_file(
            phase5_manifest_path,
            inputs.get("catf_manifest"),
            "Phase 10 CATF manifest input",
        )
        for input_name, label in (
            ("release_config", "Phase 10 release config"),
            ("evaluation_manifest", "Phase 10 evaluation manifest"),
        ):
            metadata = inputs.get(input_name)
            require(isinstance(metadata, dict), f"{label} metadata is missing")
            input_path = REPOSITORY_ROOT / str(metadata.get("path", ""))
            self._verify_file(input_path, metadata, label)
        self._verify_file(
            self.release_report_path,
            reports.get("release_readiness"),
            "Phase 10 release readiness",
        )
        report = self._load_json(
            self.release_report_path,
            "Phase 10 release readiness",
        )
        require(report.get("status") == "passed", "Phase 10 operational validation failed")
        require(
            report.get("release_evidence_version")
            == release_manifest.get("release_evidence_version"),
            "Phase 10 report version mismatch",
        )
        require(
            report.get("component4_operationally_ready") is True,
            "Component 4 operational gate did not pass",
        )
        require(
            report.get("production_ready") is False,
            "Phase 10 cannot claim production readiness before Component 2 UAT",
        )
        checks = report.get("checks")
        require(
            isinstance(checks, dict) and checks and all(checks.values()),
            "Phase 10 release checks are incomplete",
        )
        return report

    def load(self) -> None:
        manifest_path = self.artifact_dir / "manifest.json"
        scores_path = self.artifact_dir / "provider_catf_scores.csv"
        weights_path = self.artifact_dir / "category_aspect_weights.json"
        config_path = self.artifact_dir / "catf_config.json"

        manifest = self._load_json(manifest_path, "manifest")
        for version_key in (
            "catf_version",
            "weight_version",
            "category_prior_version",
            "absa_model_version",
            "credibility_model_version",
        ):
            require(bool(manifest.get(version_key)), f"Manifest lacks {version_key}")
        artifacts = manifest.get("artifacts")
        inputs = manifest.get("inputs")
        require(isinstance(artifacts, dict), "Manifest artifact metadata is missing")
        require(isinstance(inputs, dict), "Manifest input metadata is missing")
        self._verify_file(scores_path, artifacts.get("provider_scores"), "provider scores")
        self._verify_file(
            weights_path,
            artifacts.get("category_aspect_weights"),
            "category aspect weights",
        )
        self._verify_file(config_path, artifacts.get("catf_config"), "CATF config")
        self._verify_file(
            self.category_priors_path,
            inputs.get("category_priors"),
            "category priors",
        )

        config = self._load_json(config_path, "CATF config")
        profiles = self._load_json(weights_path, "category aspect weights")
        priors = self._load_json(self.category_priors_path, "category priors")
        require(config.get("version") == manifest["catf_version"], "CATF version mismatch")
        require(profiles.get("version") == manifest["weight_version"], "Weight version mismatch")
        require(
            priors.get("version") == manifest["category_prior_version"],
            "Category-prior version mismatch",
        )
        require(int(config.get("maximum_candidates", 0)) == 10, "Maximum candidates must be ten")
        require(int(config.get("maximum_top_k", 0)) == 5, "Maximum top_k must be five")

        default_weights = profiles.get("default")
        categories = profiles.get("categories")
        require(isinstance(default_weights, dict), "Default category weights are missing")
        require(isinstance(categories, dict) and categories, "Category weight profiles are missing")
        for category, weights in {"default": default_weights, **categories}.items():
            require(set(weights) == set(ASPECTS), f"Invalid aspect weights for {category}")
            values = [finite_float(weights[aspect], f"{category}.{aspect}") for aspect in ASPECTS]
            require(
                all(0 <= value <= 1 for value in values),
                f"Weights out of range for {category}",
            )
            require(math.isclose(sum(values), 1.0), f"Weights do not sum to one for {category}")

        prior_categories = priors.get("categories")
        require(isinstance(prior_categories, dict), "Category priors are missing")
        default_prior = finite_float(priors.get("default_prior"), "default_prior")
        require(0 <= default_prior <= 1, "Default category prior is out of range")

        required_columns = {
            "provider_id",
            "provider_name",
            "category",
            "district",
            "city",
            "component1_rating",
            "component1_review_count",
            "review_count",
            "effective_review_count",
            "mean_credibility",
            "reliability_factor",
            "category_prior",
            "final_catf_score",
            "evidence_status",
            "score_source",
            *[f"{aspect}_score" for aspect in ASPECTS],
        }
        provider_scores: dict[str, dict[str, Any]] = {}
        try:
            with scores_path.open(encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                require(
                    reader.fieldnames is not None
                    and required_columns.issubset(reader.fieldnames),
                    "Provider score CSV schema is incomplete",
                )
                for row in reader:
                    provider_id = str(row["provider_id"])
                    require(provider_id not in provider_scores, "Provider score IDs must be unique")
                    final_score = finite_float(row["final_catf_score"], "final_catf_score")
                    mean_credibility = finite_float(
                        row["mean_credibility"], "mean_credibility"
                    )
                    reliability = finite_float(
                        row["reliability_factor"], "reliability_factor"
                    )
                    require(0 <= final_score <= 1, "Final CATF score is out of range")
                    require(0 <= mean_credibility <= 1, "Mean credibility is out of range")
                    require(0 <= reliability <= 1, "Reliability factor is out of range")
                    aspect_scores = {
                        aspect: finite_float(row[f"{aspect}_score"], f"{aspect}_score")
                        for aspect in ASPECTS
                    }
                    require(
                        all(-1 <= value <= 1 for value in aspect_scores.values()),
                        "Aspect score is out of range",
                    )
                    provider_scores[provider_id] = {
                        "provider_id": provider_id,
                        "provider_name": row["provider_name"],
                        "category": row["category"],
                        "district": row["district"],
                        "city": row["city"],
                        "final_score": final_score,
                        "aspect_scores": aspect_scores,
                        "mean_credibility": mean_credibility,
                        "review_count": int(row["review_count"]),
                        "effective_review_count": finite_float(
                            row["effective_review_count"],
                            "effective_review_count",
                        ),
                        "reliability_factor": reliability,
                        "evidence_status": row["evidence_status"],
                        "score_source": row["score_source"],
                        "platform_rating": finite_float(
                            row["component1_rating"],
                            "component1_rating",
                        ),
                        "platform_review_count": int(row["component1_review_count"]),
                    }
        except OSError as error:
            raise ArtifactsUnavailableError("Provider scores could not be read") from error
        require(
            len(provider_scores) == int(manifest["preservation"]["component1_providers"]),
            "Provider score count differs from the manifest",
        )
        evaluation = self._load_evaluation(manifest_path)
        release_evidence = self._load_release_evidence(manifest_path)

        self.manifest = manifest
        self.config = config
        self.weight_profiles = profiles
        self.category_priors = priors
        self.provider_scores = provider_scores
        self.evaluation = evaluation
        self.release_evidence = release_evidence
        self.ready = True

    def status(self) -> dict[str, Any]:
        require(self.ready, "Component 4 artifacts are not loaded")
        return {
            "ready": True,
            "component_version": COMPONENT_VERSION,
            "provider_score_count": len(self.provider_scores),
            "versions": self.versions,
            "weight_validation_status": self.weight_profiles["validation_status"],
            "evaluation_version": self.evaluation.get("evaluation_version"),
            "ranking_ground_truth_validation": self.evaluation.get(
                "ranking_ground_truth_validation",
                "pending_phase8",
            ),
            "production_ground_truth_validation": self.evaluation.get(
                "production_ground_truth_validation",
                "pending_real_component2_and_independent_relevance_judgements",
            ),
        }

    def integration_readiness(self) -> dict[str, Any]:
        require(self.ready, "Component 4 artifacts are not loaded")
        return {
            "phase": "phase9",
            "status": "awaiting_component2",
            "component4_ready": True,
            "component2_connected": False,
            "production_ready": False,
            "contract_version": "component2-to-component4-v1",
            "expected_source": "component2",
            "maximum_input_candidates": int(self.config["maximum_candidates"]),
            "maximum_output_providers": int(self.config["maximum_top_k"]),
            "fixture_policy": "development_only",
            "required_handoff_fields": [
                "source",
                "request_id",
                "user_id",
                "component_version",
                "model_version",
                "provider_ids",
            ],
            "detail": (
                "Component 4 is ready, but production integration is waiting for the real "
                "Component 2 Top-10 implementation."
            ),
        }

    def release_readiness(self) -> dict[str, Any]:
        require(self.ready, "Component 4 artifacts are not loaded")
        require(bool(self.release_evidence), "Phase 10 release evidence is unavailable")
        return {
            "phase": "phase10",
            "release_evidence_version": self.release_evidence[
                "release_evidence_version"
            ],
            "status": self.release_evidence["production_status"],
            "component4_operationally_ready": self.release_evidence[
                "component4_operationally_ready"
            ],
            "component2_connected": self.release_evidence["component2_connected"],
            "production_ready": self.release_evidence["production_ready"],
            "checks": self.release_evidence["checks"],
            "performance": self.release_evidence["performance"],
            "thresholds": self.release_evidence["thresholds"],
            "remaining_production_gates": self.release_evidence[
                "remaining_production_gates"
            ],
            "detail": (
                "Component 4 passed its in-process operational gate. Production remains "
                "closed until real Component 2 UAT and infrastructure load testing pass."
            ),
        }

    def handoff_readiness(self) -> dict[str, Any]:
        require(self.ready, "Component 4 artifacts are not loaded")
        return {
            "phase": "phase11",
            "status": "contract_ready_awaiting_component2",
            "contract_version": "component2-to-component4-v1",
            "contract_enforced": True,
            "identity_binding_enforced": True,
            "lineage_persistence_enabled": True,
            "fixture_blocked_in_production": True,
            "component2_connected": False,
            "production_ready": False,
            "required_handoff_fields": [
                "source",
                "request_id",
                "user_id",
                "component_version",
                "model_version",
                "provider_ids",
            ],
            "detail": (
                "Component 4 enforces and persists the handoff lineage contract. "
                "Production remains closed until the real Component 2 adapter passes UAT."
            ),
        }

    def final_readiness(self) -> dict[str, Any]:
        require(self.ready, "Component 4 artifacts are not loaded")
        require(bool(self.release_evidence), "Phase 10 release evidence is unavailable")
        return {
            "phase": "phase12",
            "status": "component4_release_candidate_external_gates_pending",
            "component4_release_candidate_ready": True,
            "component2_connected": False,
            "external_api_load_test_passed": False,
            "production_ready": False,
            "checks": {
                "artifact_integrity": True,
                "held_out_ranking_evaluation": bool(self.evaluation),
                "in_process_operational_gate": bool(
                    self.release_evidence.get("component4_operationally_ready")
                ),
                "handoff_contract_enforced": True,
                "identity_binding_enforced": True,
                "lineage_persistence_enabled": True,
                "runtime_observability_available": True,
                "external_load_test_harness_available": True,
            },
            "pending_external_gates": [
                "real Component 2 Top-10 API adapter",
                "real Component 2 to Component 4 UAT",
                "external API load test against the deployed service and shared MongoDB",
            ],
            "detail": (
                "Component 4 is a validated release candidate. Whole-pipeline production "
                "readiness remains closed until the external Component 2 and infrastructure "
                "gates pass."
            ),
        }

    def weight_profile(self, category: str) -> dict[str, Any]:
        normalized = " ".join(category.split())
        categories = self.weight_profiles["categories"]
        if normalized in categories:
            weights = categories[normalized]
            source = "category_profile"
        else:
            weights = self.weight_profiles["default"]
            source = "default_profile"
        return {
            "category": normalized,
            "weights": {aspect: float(weights[aspect]) for aspect in ASPECTS},
            "profile_source": source,
            "weight_version": self.weight_profiles["version"],
            "validation_status": self.weight_profiles["validation_status"],
        }

    def _live_provider_fallback(self, provider: dict[str, Any]) -> dict[str, Any]:
        category = str(provider.get("category", "")).strip()
        profile = self.category_priors["categories"].get(category)
        prior = (
            finite_float(profile["prior"], f"{category}.prior")
            if isinstance(profile, dict)
            else finite_float(self.category_priors["default_prior"], "default_prior")
        )
        return {
            "provider_id": str(provider["provider_id"]),
            "provider_name": str(provider.get("provider_name", provider["provider_id"])),
            "category": category,
            "district": str(provider.get("district", "")),
            "city": str(provider.get("city", "")),
            "final_score": prior,
            "aspect_scores": {aspect: 0.0 for aspect in ASPECTS},
            "mean_credibility": 0.0,
            "review_count": 0,
            "effective_review_count": 0.0,
            "reliability_factor": 0.0,
            "evidence_status": "insufficient",
            "score_source": "category_prior",
            "platform_rating": finite_float(provider.get("rating", 0), "rating"),
            "platform_review_count": int(provider.get("review_count", 0)),
        }

    def provider_trust_snapshot(
        self,
        provider_id: str,
        live_provider: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        require(self.ready, "Component 4 artifacts are not loaded")
        if provider_id in self.provider_scores:
            return dict(self.provider_scores[provider_id])
        if live_provider is not None and live_provider.get("provider_id") == provider_id:
            return self._live_provider_fallback(live_provider)
        raise UnknownProviderError([provider_id])

    def rank(
        self,
        payload: Component4RankRequest,
        live_providers: list[dict[str, Any]],
    ) -> dict[str, Any]:
        require(self.ready, "Component 4 artifacts are not loaded")
        live_index = {
            str(provider["provider_id"]): provider
            for provider in live_providers
            if provider.get("provider_id")
        }
        candidates: list[dict[str, Any]] = []
        unknown: list[str] = []
        for provider_id in payload.provider_ids:
            static = self.provider_scores.get(provider_id)
            if static is not None:
                candidate = dict(static)
                live = live_index.get(provider_id)
                if live is not None and int(live.get("review_count", 0)) > 0:
                    platform_rating = finite_float(live.get("rating", 0), "rating")
                    candidate["platform_rating"] = platform_rating
                    candidate["platform_review_count"] = int(live.get("review_count", 0))
                    candidate["final_score"] = min(
                        1.0,
                        max(
                            0.0,
                            float(candidate["final_score"]) * 0.90
                            + (platform_rating / 5.0) * 0.10,
                        ),
                    )
                candidates.append(candidate)
            elif provider_id in live_index:
                candidates.append(self._live_provider_fallback(live_index[provider_id]))
            else:
                unknown.append(provider_id)
        if unknown:
            raise UnknownProviderError(sorted(unknown))

        ranked = sorted(
            candidates,
            key=lambda item: (
                -float(item["final_score"]),
                -float(item["effective_review_count"]),
                -float(item["mean_credibility"]),
                str(item["provider_id"]),
            ),
        )
        selected_count = min(payload.top_k, len(ranked))
        cutoff_score = (
            float(ranked[selected_count - 1]["final_score"])
            if selected_count
            else 0.0
        )
        evaluated_providers = []
        for rank, provider in enumerate(ranked, start=1):
            selected = rank <= selected_count
            if selected:
                reason = (
                    f"Ranked #{rank} by final CATF trust score "
                    f"{float(provider['final_score']):.4f}. Tie-breakers are effective "
                    f"review count ({float(provider['effective_review_count']):.2f}) "
                    f"then mean credibility ({float(provider['mean_credibility']):.4f}). "
                    f"Evidence source: {provider['score_source']}; evidence status: "
                    f"{provider['evidence_status']}."
                )
            else:
                reason = (
                    f"Not selected because CATF rank #{rank} was outside the requested "
                    f"Top-{selected_count} cutoff. Final CATF trust score "
                    f"{float(provider['final_score']):.4f} was below the cutoff score "
                    f"{cutoff_score:.4f}. Tie-breakers are effective review count "
                    f"({float(provider['effective_review_count']):.2f}) then mean "
                    f"credibility ({float(provider['mean_credibility']):.4f}). Evidence "
                    f"source: {provider['score_source']}; evidence status: "
                    f"{provider['evidence_status']}."
                )
            evaluated_providers.append(
                {
                    **provider,
                    "rank": rank,
                    "ranking_decision": "selected" if selected else "outside_top5",
                    "ranking_reason": reason,
                }
            )
        providers = evaluated_providers[:selected_count]
        canonical = {
            "source": payload.source,
            "request_id": payload.request_id,
            "user_id": payload.user_id,
            "source_component_version": payload.component_version,
            "source_model_version": payload.model_version,
            "provider_ids": sorted(payload.provider_ids),
            "top_k": payload.top_k,
            **self.versions,
        }
        digest = hashlib.sha256(
            json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()[:16]
        return {
            "component_version": COMPONENT_VERSION,
            "request_id": payload.request_id,
            "run_id": f"C4RUN-{digest.upper()}",
            "handoff": {
                "source": payload.source,
                "request_id": payload.request_id,
                "user_id": payload.user_id,
                "component_version": payload.component_version,
                "model_version": payload.model_version,
            },
            "input_count": len(payload.provider_ids),
            "output_count": len(providers),
            "requested_top_k": payload.top_k,
            "candidate_provider_ids": payload.provider_ids,
            "providers": providers,
            "evaluated_providers": evaluated_providers,
            "versions": self.versions,
        }


class Component4RankingOrchestrator:
    def __init__(
        self,
        engine: Component4RankingEngine,
        repository: Component4Repository,
    ) -> None:
        self.engine = engine
        self.repository = repository

    async def rank(
        self,
        payload: Component4RankRequest,
        *,
        user_id: str,
        live_providers: list[dict[str, Any]],
    ) -> Component4RankResponse:
        started = time.perf_counter()
        ranking = self.engine.rank(payload, live_providers)
        if not payload.force_recalculate:
            cached = await self.repository.find_completed_response(
                ranking["run_id"],
                user_id,
            )
            if cached is not None:
                cached = {**cached, "cached": True}
                return Component4RankResponse.model_validate(cached)

        processing_time_ms = (time.perf_counter() - started) * 1000
        response = Component4RankResponse.model_validate(
            {
                **ranking,
                "user_id": user_id,
                "cached": False,
                "processing_time_ms": processing_time_ms,
            }
        )
        response_payload = response.model_dump(mode="json")
        run_document = {
            "run_id": response.run_id,
            "request_id": response.request_id,
            "user_id": user_id,
            "handoff": response.handoff.model_dump(),
            "candidate_provider_ids": response.candidate_provider_ids,
            "input_count": response.input_count,
            "output_count": response.output_count,
            "requested_top_k": response.requested_top_k,
            "force_recalculate": payload.force_recalculate,
            **response.versions.model_dump(),
            "component_version": response.component_version,
            "processing_time_ms": response.processing_time_ms,
            "response": response_payload,
        }
        created_at = utc_now()
        persisted_providers = response.evaluated_providers or response.providers
        provider_documents = [
            {
                "run_id": response.run_id,
                "request_id": response.request_id,
                "user_id": user_id,
                "handoff": response.handoff.model_dump(),
                "provider_id": provider.provider_id,
                "provider_name": provider.provider_name,
                "category": provider.category,
                "rank": provider.rank,
                "final_catf_score": provider.final_score,
                "aspect_scores": provider.aspect_scores.model_dump(),
                "mean_credibility": provider.mean_credibility,
                "review_count": provider.review_count,
                "effective_review_count": provider.effective_review_count,
                "reliability_factor": provider.reliability_factor,
                "evidence_status": provider.evidence_status,
                "score_source": provider.score_source,
                "ranking_reason": provider.ranking_reason,
                "ranking_decision": provider.ranking_decision,
                "created_at": created_at,
                **response.versions.model_dump(),
            }
            for provider in persisted_providers
        ]
        await self.repository.persist_completed(run_document, provider_documents)
        return response


@lru_cache
def get_component4_engine(
    artifact_dir: Path,
    category_priors_path: Path,
) -> Component4RankingEngine:
    engine = Component4RankingEngine(artifact_dir, category_priors_path)
    engine.load()
    return engine
