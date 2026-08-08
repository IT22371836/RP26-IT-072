from __future__ import annotations

import sys
from pathlib import Path

import numpy as np


COMPONENT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = COMPONENT_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

import train_credibility  # noqa: E402
from credibility_inference import CredibilityInference  # noqa: E402


def test_feature_contract_excludes_targets_and_identifiers() -> None:
    forbidden = {
        "is_fake_review",
        "credibility_score",
        "review_id",
        "provider_id",
        "source_provider_id",
        "dataset_split",
    }
    assert not forbidden.intersection(train_credibility.FEATURE_COLUMNS)


def test_phase4_dataset_contract_preserves_phase2_rows_and_splits() -> None:
    frame = train_credibility.load_dataset(
        train_credibility.DEFAULT_REVIEWS,
        train_credibility.DEFAULT_CREDIBILITY,
    )

    assert len(frame) == 25_000
    assert frame["review_id"].nunique() == 25_000
    assert frame["source_provider_id"].nunique() == 4_976
    assert set(frame["dataset_split"]) == {"train", "validation", "test"}
    assert frame.groupby("review_text_group_id")["dataset_split"].nunique().max() == 1


def test_threshold_selection_is_deterministic() -> None:
    actual = np.asarray([0, 0, 0, 1, 1, 1], dtype=np.int32)
    normality = np.asarray([0.8, 0.7, 0.6, 0.4, 0.3, 0.2])

    first = train_credibility.select_fake_threshold(actual, normality)
    second = train_credibility.select_fake_threshold(actual, normality)

    assert first[0] == second[0]
    assert first[1] == second[1]
    np.testing.assert_array_equal(
        train_credibility.predict_fake(normality, first[0]),
        actual,
    )


def test_train_only_normalization_is_bounded_and_batch_independent() -> None:
    scores = np.asarray([-0.9, -0.5, -0.1])
    together = train_credibility.normality_to_credibility(scores, -0.8, -0.2)
    separately = np.concatenate(
        [
            train_credibility.normality_to_credibility(
                np.asarray([score]),
                -0.8,
                -0.2,
            )
            for score in scores
        ]
    )

    np.testing.assert_allclose(together, separately)
    assert np.all((together >= 0) & (together <= 1))
    np.testing.assert_allclose(together, [0.0, 0.5, 1.0])


def test_smoke_training_exports_reloadable_pipeline(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "artifacts"
    report_dir = tmp_path / "reports"
    config = train_credibility.smoke_config(train_credibility.CredibilityConfig())
    manifest = train_credibility.train(
        train_credibility.DEFAULT_REVIEWS,
        train_credibility.DEFAULT_CREDIBILITY,
        artifact_dir,
        report_dir,
        config,
    )

    assert manifest["smoke_test"] is True
    assert manifest["preservation"]["input_reviews"] == 25_000
    assert manifest["preservation"]["modeled_reviews"] == 1_600
    assert manifest["preservation"]["output_predictions"] == 1_600
    inference = CredibilityInference(artifact_dir)
    source = train_credibility.load_dataset(
        train_credibility.DEFAULT_REVIEWS,
        train_credibility.DEFAULT_CREDIBILITY,
    ).head(3)
    predicted = inference.predict(source)
    assert len(predicted) == 3
    assert predicted["predicted_credibility_score"].between(0, 1).all()
    assert set(predicted["predicted_is_fake_review"]).issubset({0, 1})
