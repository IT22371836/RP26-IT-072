"""Deterministically reduce Component 2 candidate IDs to Component 4 final providers."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import pandas as pd

from catf_service import ASPECTS, load_catf_config


COMPONENT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROVIDER_SCORES = (
    COMPONENT_ROOT / "artifacts" / "catf-v1" / "provider_catf_scores.csv"
)
DEFAULT_CATF_MANIFEST = COMPONENT_ROOT / "artifacts" / "catf-v1" / "manifest.json"


class CATFRankingError(ValueError):
    """Raised when the Top-10-to-Top-5 ranking contract is violated."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CATFRankingError(message)


class CATFRanker:
    """Validated in-memory ranking snapshot for deterministic candidate filtering."""

    def __init__(
        self,
        scores_path: Path = DEFAULT_PROVIDER_SCORES,
        manifest_path: Path = DEFAULT_CATF_MANIFEST,
    ) -> None:
        require(scores_path.is_file(), f"provider score artifact is missing: {scores_path}")
        require(manifest_path.is_file(), f"CATF manifest is missing: {manifest_path}")
        self.scores_path = scores_path.resolve()
        self.manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.config = load_catf_config()
        self.scores = pd.read_csv(self.scores_path)
        required = {
            "provider_id",
            "provider_name",
            "category",
            "district",
            "final_catf_score",
            "effective_review_count",
            "mean_credibility",
            "reliability_factor",
            "review_count",
            "evidence_status",
            "score_source",
            *[f"{aspect}_score" for aspect in ASPECTS],
        }
        require(
            required.issubset(self.scores.columns),
            f"provider scores lack columns: {sorted(required - set(self.scores.columns))}",
        )
        require(self.scores["provider_id"].is_unique, "provider score IDs must be unique")
        require(
            self.scores["final_catf_score"].between(0, 1).all(),
            "final CATF scores must be bounded 0..1",
        )
        numeric = self.scores[
            [
                "final_catf_score",
                "effective_review_count",
                "mean_credibility",
                "reliability_factor",
            ]
        ].to_numpy(dtype=np.float64)
        require(np.isfinite(numeric).all(), "ranking values must be finite")
        self._provider_ids = set(self.scores["provider_id"])

    def rank(
        self,
        provider_ids: Sequence[str],
        *,
        request_id: str,
        top_k: int = 5,
    ) -> dict[str, Any]:
        candidates = [str(provider_id).strip() for provider_id in provider_ids]
        require(bool(str(request_id).strip()), "request_id is required")
        require(1 <= len(candidates) <= int(self.config["maximum_candidates"]), "supply 1..10 candidates")
        require(all(candidates), "provider IDs cannot be empty")
        require(len(candidates) == len(set(candidates)), "provider IDs must be unique")
        require(1 <= int(top_k) <= int(self.config["maximum_top_k"]), "top_k must be 1..5")
        unknown = sorted(set(candidates) - self._provider_ids)
        require(not unknown, f"unknown provider IDs: {unknown}")

        candidate_set = set(candidates)
        selected = self.scores[self.scores["provider_id"].isin(candidate_set)].copy()
        require(len(selected) == len(candidates), "candidate retrieval changed the input count")
        ranked = selected.sort_values(
            [
                "final_catf_score",
                "effective_review_count",
                "mean_credibility",
                "provider_id",
            ],
            ascending=[False, False, False, True],
            kind="stable",
        ).head(min(int(top_k), len(selected)))
        require(set(ranked["provider_id"]).issubset(candidate_set), "ranking added a non-candidate provider")

        canonical_run = {
            "request_id": str(request_id).strip(),
            "provider_ids": sorted(candidates),
            "top_k": int(top_k),
            "catf_version": self.manifest["catf_version"],
            "weight_version": self.manifest["weight_version"],
            "category_prior_version": self.manifest["category_prior_version"],
            "absa_model_version": self.manifest["absa_model_version"],
            "credibility_model_version": self.manifest["credibility_model_version"],
        }
        run_digest = hashlib.sha256(
            json.dumps(canonical_run, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()[:16].upper()
        providers: list[dict[str, Any]] = []
        for rank, (_, row) in enumerate(ranked.iterrows(), start=1):
            providers.append(
                {
                    "provider_id": row["provider_id"],
                    "provider_name": row["provider_name"],
                    "category": row["category"],
                    "district": row["district"],
                    "rank": rank,
                    "final_score": float(row["final_catf_score"]),
                    "aspect_scores": {
                        aspect: float(row[f"{aspect}_score"]) for aspect in ASPECTS
                    },
                    "mean_credibility": float(row["mean_credibility"]),
                    "review_count": int(row["review_count"]),
                    "effective_review_count": float(row["effective_review_count"]),
                    "reliability_factor": float(row["reliability_factor"]),
                    "evidence_status": row["evidence_status"],
                    "score_source": row["score_source"],
                }
            )
        return {
            "request_id": str(request_id).strip(),
            "run_id": f"C4RUN-{run_digest}",
            "input_count": len(candidates),
            "output_count": len(providers),
            "requested_top_k": int(top_k),
            "candidate_provider_ids": candidates,
            "providers": providers,
            "versions": {
                key: canonical_run[key]
                for key in (
                    "catf_version",
                    "weight_version",
                    "category_prior_version",
                    "absa_model_version",
                    "credibility_model_version",
                )
            },
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider-ids", nargs="+", required=True)
    parser.add_argument("--request-id", required=True)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--scores", type=Path, default=DEFAULT_PROVIDER_SCORES)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_CATF_MANIFEST)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = CATFRanker(args.scores, args.manifest).rank(
        args.provider_ids,
        request_id=args.request_id,
        top_k=args.top_k,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
