"""Load the versioned Component 4 ABSA model and run raw-text inference."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import pandas as pd
import tensorflow as tf
from tensorflow import keras

from train_absa import ASPECTS, LABEL_ORDER, sha256_file


COMPONENT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ARTIFACT_DIR = COMPONENT_ROOT / "artifacts" / "absa-v1"


class ABSAArtifactError(ValueError):
    """Raised when the saved Phase 3 artifact contract is invalid."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ABSAArtifactError(message)


class ABSAInference:
    """Validated, reusable inference wrapper for the four ABSA output heads."""

    def __init__(self, artifact_dir: Path = DEFAULT_ARTIFACT_DIR) -> None:
        self.artifact_dir = artifact_dir.resolve()
        manifest_path = self.artifact_dir / "manifest.json"
        label_mapping_path = self.artifact_dir / "label_mapping.json"
        model_path = self.artifact_dir / "absa_model.keras"

        require(manifest_path.is_file(), f"missing artifact manifest: {manifest_path}")
        require(label_mapping_path.is_file(), f"missing label mapping: {label_mapping_path}")
        require(model_path.is_file(), f"missing ABSA model: {model_path}")

        self.manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.label_mapping = json.loads(label_mapping_path.read_text(encoding="utf-8"))
        require(
            tuple(self.label_mapping.get("label_order", ())) == LABEL_ORDER,
            f"label order must be {list(LABEL_ORDER)}",
        )
        require(
            tuple(self.label_mapping.get("aspect_output_names", ())) == ASPECTS,
            f"aspect outputs must be {list(ASPECTS)}",
        )

        expected_hash = (
            self.manifest.get("artifacts", {}).get("model", {}).get("sha256")
        )
        require(bool(expected_hash), "manifest has no model SHA-256")
        require(
            sha256_file(model_path) == expected_hash,
            "model SHA-256 does not match the Phase 3 manifest",
        )
        self.model = keras.models.load_model(model_path, compile=False)
        require(
            set(self.model.output_names) == set(ASPECTS),
            f"model output heads differ from {list(ASPECTS)}",
        )

    def predict(
        self,
        review_texts: Sequence[str],
        *,
        batch_size: int = 64,
    ) -> list[dict[str, Any]]:
        """Predict labels, confidence, probabilities, and signed sentiment scores."""

        texts = [str(text).strip() for text in review_texts]
        require(bool(texts), "at least one review is required")
        require(all(texts), "review text cannot be empty")
        raw_predictions = self.model.predict(
            tf.constant(texts, dtype=tf.string),
            batch_size=batch_size,
            verbose=0,
        )
        require(isinstance(raw_predictions, dict), "ABSA prediction must be a mapping")

        results: list[dict[str, Any]] = []
        for row_index, text in enumerate(texts):
            result: dict[str, Any] = {"review_text": text, "aspects": {}}
            for aspect in ASPECTS:
                probabilities = np.asarray(raw_predictions[aspect][row_index], dtype=float)
                require(
                    probabilities.shape == (len(LABEL_ORDER),),
                    f"unexpected {aspect} probability shape: {probabilities.shape}",
                )
                predicted_index = int(probabilities.argmax())
                result["aspects"][aspect] = {
                    "label": LABEL_ORDER[predicted_index],
                    "confidence": float(probabilities[predicted_index]),
                    "sentiment_score": float(probabilities[0] - probabilities[2]),
                    "probabilities": {
                        label: float(probabilities[index])
                        for index, label in enumerate(LABEL_ORDER)
                    },
                }
            results.append(result)
        return results


def flatten_predictions(predictions: list[dict[str, Any]]) -> pd.DataFrame:
    """Flatten API-shaped predictions into a CSV-friendly table."""

    rows: list[dict[str, Any]] = []
    for prediction in predictions:
        row: dict[str, Any] = {"review_text": prediction["review_text"]}
        for aspect, values in prediction["aspects"].items():
            row[f"{aspect}_label"] = values["label"]
            row[f"{aspect}_confidence"] = values["confidence"]
            row[f"{aspect}_sentiment_score"] = values["sentiment_score"]
            for label, probability in values["probabilities"].items():
                row[f"{aspect}_{label.lower()}_probability"] = probability
        rows.append(row)
    return pd.DataFrame(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-dir", type=Path, default=DEFAULT_ARTIFACT_DIR)
    parser.add_argument("--text", action="append", help="Review text; may be supplied repeatedly")
    parser.add_argument("--input-csv", type=Path)
    parser.add_argument("--text-column", default="review_text")
    parser.add_argument("--output-csv", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    texts = list(args.text or [])
    if args.input_csv:
        frame = pd.read_csv(args.input_csv)
        require(args.text_column in frame.columns, f"missing column: {args.text_column}")
        texts.extend(frame[args.text_column].astype(str).tolist())
    require(bool(texts), "supply --text or --input-csv")

    predictions = ABSAInference(args.artifact_dir).predict(texts)
    if args.output_csv:
        args.output_csv.parent.mkdir(parents=True, exist_ok=True)
        flatten_predictions(predictions).to_csv(
            args.output_csv,
            index=False,
            lineterminator="\n",
        )
        print(f"Predictions: {args.output_csv.resolve()}")
    else:
        print(json.dumps(predictions, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
