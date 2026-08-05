from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


tf = pytest.importorskip("tensorflow")

COMPONENT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = COMPONENT_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

import train_absa  # noqa: E402


def tiny_config() -> train_absa.TrainingConfig:
    return train_absa.TrainingConfig(
        max_tokens=100,
        sequence_length=12,
        embedding_dim=8,
        lstm_units=4,
        attention_heads=2,
        attention_key_dim=2,
        attention_dropout=0.0,
        encoder_dropout=0.0,
        shared_dropout=0.0,
        dense_units=8,
        batch_size=2,
        epochs=1,
    )


def test_fixed_label_order_supports_downstream_sentiment_formula() -> None:
    assert train_absa.LABEL_ORDER == ("Positive", "Neutral", "Negative")
    assert train_absa.LABEL_TO_ID == {"Positive": 0, "Neutral": 1, "Negative": 2}


def test_embedded_standardizer_handles_noise_and_preserves_sinhala() -> None:
    standardized = train_absa.standardize_review_text(
        tf.constant(["GOOD <b>වැඩක්</b> https://example.com test@example.com can't"])
    ).numpy()[0].decode("utf-8")

    assert "https" not in standardized
    assert "example.com" not in standardized
    assert "urltoken" in standardized
    assert "emailtoken" in standardized
    assert "වැඩක්" in standardized
    assert "can't" in standardized


def test_model_has_true_multi_head_attention_and_four_probability_heads() -> None:
    config = tiny_config()
    vectorizer = train_absa.build_vectorizer(
        pd.Series(["excellent service", "late but polite", "වැඩේ හොඳයි"]),
        config,
    )
    model = train_absa.build_model(vectorizer, config)

    attention = model.get_layer("multi_head_self_attention")
    assert isinstance(attention, tf.keras.layers.MultiHeadAttention)
    assert set(model.output_names) == set(train_absa.ASPECTS)

    predictions = model.predict(tf.constant(["excellent and professional"]), verbose=0)
    assert isinstance(predictions, dict)
    for aspect in train_absa.ASPECTS:
        assert predictions[aspect].shape == (1, 3)
        np.testing.assert_allclose(predictions[aspect].sum(axis=1), [1.0], atol=1e-5)


def test_saved_model_reloads_with_embedded_preprocessing(tmp_path: Path) -> None:
    config = tiny_config()
    vectorizer = train_absa.build_vectorizer(
        pd.Series(["excellent service", "poor communication", "arrived on time"]),
        config,
    )
    model = train_absa.build_model(vectorizer, config)
    model_path = tmp_path / "test_absa.keras"
    model.save(model_path)

    loaded = tf.keras.models.load_model(model_path, compile=False)
    predictions = loaded.predict(tf.constant(["clean raw review text"]), verbose=0)
    assert isinstance(predictions, dict)
    assert set(predictions) == set(train_absa.ASPECTS)


def test_phase3_dataset_contract_preserves_all_phase2_reviews() -> None:
    frame = train_absa.load_dataset(
        train_absa.DEFAULT_REVIEWS,
        train_absa.DEFAULT_LABELS,
    )

    assert len(frame) == 25_000
    assert frame["review_id"].nunique() == 25_000
    assert frame["source_provider_id"].nunique() == 4_976
    assert set(frame["dataset_split"]) == {"train", "validation", "test"}
