"""Load the Phase 4 credibility artifact and score review-feature rows."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from train_credibility import (
    DEFAULT_ARTIFACT_DIR,
    FEATURE_COLUMNS,
    FEATURE_CONTRACT_VERSION,
    MODEL_VERSION,
    normality_to_credibility,
    predict_fake,
    sha256_file,
)


class CredibilityArtifactError(ValueError):
    """Raised when a Phase 4 artifact or inference input is invalid."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CredibilityArtifactError(message)


class CredibilityInference:
    """Validated reusable wrapper around the credibility preprocessing/model bundle."""

    def __init__(self, artifact_dir: Path = DEFAULT_ARTIFACT_DIR) -> None:
        self.artifact_dir = artifact_dir.resolve()
        manifest_path = self.artifact_dir / "manifest.json"
        contract_path = self.artifact_dir / "feature_contract.json"
        pipeline_path = self.artifact_dir / "credibility_pipeline.joblib"
        require(manifest_path.is_file(), f"missing credibility manifest: {manifest_path}")
        require(contract_path.is_file(), f"missing feature contract: {contract_path}")
        require(pipeline_path.is_file(), f"missing credibility pipeline: {pipeline_path}")

        self.manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.feature_contract = json.loads(contract_path.read_text(encoding="utf-8"))
        require(
            self.manifest.get("model_version") == MODEL_VERSION,
            f"unsupported model version: {self.manifest.get('model_version')}",
        )
        require(
            self.feature_contract.get("version") == FEATURE_CONTRACT_VERSION,
            "feature contract version mismatch",
        )
        require(
            tuple(self.feature_contract.get("input_features", ())) == FEATURE_COLUMNS,
            "feature order differs from the Phase 4 contract",
        )
        expected_hash = (
            self.manifest.get("artifacts", {}).get("pipeline", {}).get("sha256")
        )
        require(bool(expected_hash), "manifest has no pipeline SHA-256")
        require(
            sha256_file(pipeline_path) == expected_hash,
            "pipeline SHA-256 does not match the Phase 4 manifest",
        )

        self.bundle: dict[str, Any] = joblib.load(pipeline_path)
        require(
            self.bundle.get("model_version") == MODEL_VERSION,
            "pipeline model version mismatch",
        )
        require(
            tuple(self.bundle.get("feature_columns", ())) == FEATURE_COLUMNS,
            "pipeline feature order mismatch",
        )

    def predict(self, features: pd.DataFrame) -> pd.DataFrame:
        """Return the input rows plus stable credibility and fake-review predictions."""

        missing = set(FEATURE_COLUMNS) - set(features.columns)
        require(not missing, f"missing credibility features: {sorted(missing)}")
        numeric = features[list(FEATURE_COLUMNS)].apply(pd.to_numeric, errors="coerce")
        require(numeric.notna().all().all(), "credibility features must be numeric and non-null")
        require(
            np.isfinite(numeric.to_numpy(dtype=np.float64)).all(),
            "credibility features must be finite",
        )

        scaled = self.bundle["scaler"].transform(numeric)
        normality = self.bundle["isolation_forest"].score_samples(scaled)
        predicted_credibility = normality_to_credibility(
            normality,
            float(self.bundle["normalization_lower_bound"]),
            float(self.bundle["normalization_upper_bound"]),
        )
        predicted_fake = predict_fake(
            normality,
            float(self.bundle["normality_threshold"]),
        )
        result = features.copy()
        result["isolation_normality_score"] = normality
        result["predicted_credibility_score"] = predicted_credibility
        result["predicted_is_fake_review"] = predicted_fake
        return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-dir", type=Path, default=DEFAULT_ARTIFACT_DIR)
    parser.add_argument("--input-csv", type=Path, required=True)
    parser.add_argument("--output-csv", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    frame = pd.read_csv(args.input_csv)
    predictions = CredibilityInference(args.artifact_dir).predict(frame)
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    predictions.to_csv(args.output_csv, index=False, lineterminator="\n")
    print(f"Credibility predictions: {args.output_csv.resolve()}")


if __name__ == "__main__":
    main()
