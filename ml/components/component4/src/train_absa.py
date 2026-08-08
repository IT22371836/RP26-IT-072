"""Train and evaluate the Component 4 multi-task ABSA model.

The saved Keras model accepts raw review strings and embeds its TextVectorization layer, keeping
training and inference preprocessing identical. Phase 1/2 datasets are read-only inputs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import random
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import tensorflow as tf
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    precision_recall_fscore_support,
)
from sklearn.utils.class_weight import compute_class_weight
from tensorflow import keras
from tensorflow.keras import layers


COMPONENT_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = COMPONENT_ROOT.parents[2]
DEFAULT_REVIEWS = COMPONENT_ROOT / "data" / "processed" / "customer_reviews_mapped.csv"
DEFAULT_LABELS = COMPONENT_ROOT / "data" / "processed" / "aspect_sentiment_labels_clean.csv"
DEFAULT_ARTIFACT_DIR = COMPONENT_ROOT / "artifacts" / "absa-v1"
DEFAULT_REPORT_DIR = COMPONENT_ROOT / "reports" / "absa-v1"

MODEL_VERSION = "absa-v1"
PREPROCESSING_VERSION = "text-vectorization-v1"
LABEL_MAPPING_VERSION = "aspect-labels-v1"
SEED = 42

ASPECT_TO_LABEL_COLUMN = {
    "quality": "quality_label",
    "punctuality": "punctuality_label",
    "communication": "communication_label",
    "professionalism": "professionalism_label",
}
ASPECTS = tuple(ASPECT_TO_LABEL_COLUMN)
LABEL_ORDER = ("Positive", "Neutral", "Negative")
LABEL_TO_ID = {label: index for index, label in enumerate(LABEL_ORDER)}


class ABSATrainingError(ValueError):
    """Raised when the ABSA dataset or training configuration is invalid."""


@dataclass(frozen=True)
class TrainingConfig:
    seed: int = SEED
    max_tokens: int = 15_000
    sequence_length: int = 80
    embedding_dim: int = 128
    lstm_units: int = 64
    attention_heads: int = 4
    attention_key_dim: int = 32
    attention_dropout: float = 0.20
    encoder_dropout: float = 0.25
    shared_dropout: float = 0.40
    dense_units: int = 96
    batch_size: int = 64
    epochs: int = 20
    learning_rate: float = 0.001
    early_stopping_patience: int = 3
    reduce_lr_patience: int = 2
    max_train_samples: int | None = None
    max_validation_samples: int | None = None
    max_test_samples: int | None = None
    smoke_test: bool = False


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ABSATrainingError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def file_metadata(path: Path) -> dict[str, Any]:
    try:
        display_path = path.resolve().relative_to(REPOSITORY_ROOT).as_posix()
    except ValueError:
        display_path = str(path.resolve())
    return {
        "path": display_path,
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def set_reproducibility(seed: int) -> None:
    os.environ["PYTHONHASHSEED"] = str(seed)
    random.seed(seed)
    np.random.seed(seed)
    tf.keras.utils.set_random_seed(seed)
    try:
        tf.config.experimental.enable_op_determinism()
    except (AttributeError, RuntimeError):
        pass


@keras.utils.register_keras_serializable(package="component4")
def standardize_review_text(inputs: tf.Tensor) -> tf.Tensor:
    """Apply the versioned ABSA-only standardization inside the saved model."""

    text = tf.strings.lower(inputs)
    text = tf.strings.regex_replace(text, r"(https?://\S+|www\.\S+)", " urltoken ")
    text = tf.strings.regex_replace(
        text,
        r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b",
        " emailtoken ",
    )
    text = tf.strings.regex_replace(text, r"<[^>]+>", " ")
    text = tf.strings.regex_replace(text, "[^A-Za-z0-9\u0D80-\u0DFF']+", " ")
    return tf.strings.regex_replace(text, r"\s+", " ")


def load_dataset(reviews_path: Path, labels_path: Path) -> pd.DataFrame:
    require(reviews_path.is_file(), f"mapped review dataset is missing: {reviews_path}")
    require(labels_path.is_file(), f"aspect label dataset is missing: {labels_path}")
    reviews = pd.read_csv(reviews_path)
    labels = pd.read_csv(labels_path)

    required_reviews = {
        "review_id",
        "provider_id",
        "source_provider_id",
        "review_text",
        "review_text_group_id",
        "dataset_split",
    }
    required_labels = {"review_id", *ASPECT_TO_LABEL_COLUMN.values()}
    require(
        required_reviews.issubset(reviews.columns),
        f"reviews lack columns: {sorted(required_reviews - set(reviews.columns))}",
    )
    require(
        required_labels.issubset(labels.columns),
        f"labels lack columns: {sorted(required_labels - set(labels.columns))}",
    )
    require(reviews["review_id"].is_unique, "review IDs must be unique")
    require(labels["review_id"].is_unique, "label review IDs must be unique")
    require(set(reviews["review_id"]) == set(labels["review_id"]), "review/label ID sets differ")
    require(
        reviews.groupby("review_text_group_id")["dataset_split"].nunique().max() == 1,
        "a normalized text group crosses dataset splits",
    )
    require(
        set(reviews["dataset_split"]) == {"train", "validation", "test"},
        "train, validation, and test splits are required",
    )

    label_columns = ["review_id", *ASPECT_TO_LABEL_COLUMN.values()]
    merged = reviews.merge(labels[label_columns], on="review_id", validate="one_to_one")
    require(merged["review_text"].astype(str).str.strip().ne("").all(), "empty reviews are invalid")
    for column in ASPECT_TO_LABEL_COLUMN.values():
        require(
            set(merged[column]) == set(LABEL_ORDER),
            f"{column} must contain exactly {list(LABEL_ORDER)}",
        )
    return merged


def encode_labels(frame: pd.DataFrame) -> dict[str, np.ndarray]:
    encoded: dict[str, np.ndarray] = {}
    for aspect, column in ASPECT_TO_LABEL_COLUMN.items():
        values = frame[column].map(LABEL_TO_ID)
        require(values.notna().all(), f"unknown labels found in {column}")
        encoded[aspect] = values.to_numpy(dtype=np.int32)
    return encoded


def limit_split(frame: pd.DataFrame, maximum: int | None) -> pd.DataFrame:
    if maximum is None or len(frame) <= maximum:
        return frame.reset_index(drop=True)
    return frame.sort_values("review_id", kind="stable").head(maximum).reset_index(drop=True)


def split_dataset(
    frame: pd.DataFrame, config: TrainingConfig
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    train = limit_split(
        frame[frame["dataset_split"].eq("train")], config.max_train_samples
    )
    validation = limit_split(
        frame[frame["dataset_split"].eq("validation")],
        config.max_validation_samples,
    )
    test = limit_split(frame[frame["dataset_split"].eq("test")], config.max_test_samples)
    require(not train.empty and not validation.empty and not test.empty, "all splits must be non-empty")
    return train, validation, test


def build_vectorizer(train_text: pd.Series, config: TrainingConfig) -> layers.TextVectorization:
    vectorizer = layers.TextVectorization(
        name="text_vectorization",
        max_tokens=config.max_tokens,
        standardize=standardize_review_text,
        split="whitespace",
        output_mode="int",
        output_sequence_length=config.sequence_length,
        pad_to_max_tokens=False,
    )
    adapt_dataset = tf.data.Dataset.from_tensor_slices(
        train_text.astype(str).to_numpy()
    ).batch(config.batch_size)
    vectorizer.adapt(adapt_dataset)
    return vectorizer


def build_model(
    vectorizer: layers.TextVectorization,
    config: TrainingConfig,
) -> keras.Model:
    review_text = keras.Input(shape=(), dtype=tf.string, name="review_text")
    token_ids = vectorizer(review_text)
    embedding = layers.Embedding(
        input_dim=vectorizer.vocabulary_size(),
        output_dim=config.embedding_dim,
        mask_zero=True,
        name="token_embedding",
    )(token_ids)
    encoded = layers.Bidirectional(
        layers.LSTM(
            config.lstm_units,
            return_sequences=True,
            dropout=config.encoder_dropout,
            recurrent_dropout=0.0,
        ),
        name="bidirectional_lstm",
    )(embedding)
    attended = layers.MultiHeadAttention(
        num_heads=config.attention_heads,
        key_dim=config.attention_key_dim,
        dropout=config.attention_dropout,
        name="multi_head_self_attention",
    )(encoded, encoded)
    encoded = layers.Add(name="attention_residual")([encoded, attended])
    encoded = layers.LayerNormalization(name="attention_layer_norm")(encoded)
    pooled = layers.GlobalAveragePooling1D(name="masked_global_average_pooling")(encoded)
    shared = layers.Dense(config.dense_units, activation="relu", name="shared_dense")(pooled)
    shared = layers.Dropout(config.shared_dropout, name="shared_dropout")(shared)
    outputs = {
        aspect: layers.Dense(3, activation="softmax", name=aspect)(shared)
        for aspect in ASPECTS
    }
    model = keras.Model(review_text, outputs, name="component4_multitask_bilstm_mha")
    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=config.learning_rate),
        loss={
            aspect: keras.losses.SparseCategoricalCrossentropy(name=f"{aspect}_loss")
            for aspect in ASPECTS
        },
        metrics={
            aspect: [
                keras.metrics.SparseCategoricalAccuracy(name="accuracy"),
            ]
            for aspect in ASPECTS
        },
    )
    return model


def balanced_sample_weights(labels: dict[str, np.ndarray]) -> tuple[
    dict[str, np.ndarray], dict[str, dict[str, float]]
]:
    sample_weights: dict[str, np.ndarray] = {}
    report: dict[str, dict[str, float]] = {}
    classes = np.arange(len(LABEL_ORDER), dtype=np.int32)
    for aspect, values in labels.items():
        weights = compute_class_weight(class_weight="balanced", classes=classes, y=values)
        sample_weights[aspect] = weights[values].astype(np.float32)
        report[aspect] = {
            LABEL_ORDER[index]: round(float(weight), 8)
            for index, weight in enumerate(weights)
        }
    return sample_weights, report


def make_dataset(
    frame: pd.DataFrame,
    config: TrainingConfig,
    *,
    training: bool,
    include_sample_weights: bool = False,
) -> tuple[tf.data.Dataset, dict[str, dict[str, float]] | None]:
    texts = frame["review_text"].astype(str).to_numpy()
    labels = encode_labels(frame)
    class_weight_report: dict[str, dict[str, float]] | None = None
    if include_sample_weights:
        sample_weights, class_weight_report = balanced_sample_weights(labels)
        dataset = tf.data.Dataset.from_tensor_slices((texts, labels, sample_weights))
    else:
        dataset = tf.data.Dataset.from_tensor_slices((texts, labels))
    if training:
        dataset = dataset.shuffle(
            buffer_size=len(frame),
            seed=config.seed,
            reshuffle_each_iteration=True,
        )
    dataset = dataset.batch(config.batch_size).prefetch(tf.data.AUTOTUNE)
    return dataset, class_weight_report


def evaluate_predictions(
    test: pd.DataFrame,
    probabilities: dict[str, np.ndarray],
) -> tuple[dict[str, Any], pd.DataFrame, dict[str, np.ndarray]]:
    predictions = test[
        ["review_id", "provider_id", "source_provider_id", "review_text"]
    ].copy()
    metrics: dict[str, Any] = {"aspects": {}}
    matrices: dict[str, np.ndarray] = {}
    accuracies: list[float] = []
    macro_f1_values: list[float] = []

    encoded = encode_labels(test)
    for aspect in ASPECTS:
        probability = np.asarray(probabilities[aspect])
        require(
            probability.shape == (len(test), len(LABEL_ORDER)),
            f"unexpected probability shape for {aspect}: {probability.shape}",
        )
        predicted_ids = probability.argmax(axis=1)
        actual_ids = encoded[aspect]
        precision, recall, f1, support = precision_recall_fscore_support(
            actual_ids,
            predicted_ids,
            labels=np.arange(len(LABEL_ORDER)),
            zero_division=0,
        )
        macro_precision, macro_recall, macro_f1, _ = precision_recall_fscore_support(
            actual_ids,
            predicted_ids,
            average="macro",
            zero_division=0,
        )
        weighted_precision, weighted_recall, weighted_f1, _ = (
            precision_recall_fscore_support(
                actual_ids,
                predicted_ids,
                average="weighted",
                zero_division=0,
            )
        )
        accuracy = accuracy_score(actual_ids, predicted_ids)
        matrix = confusion_matrix(
            actual_ids,
            predicted_ids,
            labels=np.arange(len(LABEL_ORDER)),
        )
        matrices[aspect] = matrix
        accuracies.append(float(accuracy))
        macro_f1_values.append(float(macro_f1))

        metrics["aspects"][aspect] = {
            "accuracy": float(accuracy),
            "macro_precision": float(macro_precision),
            "macro_recall": float(macro_recall),
            "macro_f1": float(macro_f1),
            "weighted_precision": float(weighted_precision),
            "weighted_recall": float(weighted_recall),
            "weighted_f1": float(weighted_f1),
            "per_class": {
                label: {
                    "precision": float(precision[index]),
                    "recall": float(recall[index]),
                    "f1": float(f1[index]),
                    "support": int(support[index]),
                }
                for index, label in enumerate(LABEL_ORDER)
            },
            "classification_report": classification_report(
                actual_ids,
                predicted_ids,
                labels=np.arange(len(LABEL_ORDER)),
                target_names=list(LABEL_ORDER),
                output_dict=True,
                zero_division=0,
            ),
            "confusion_matrix": matrix.tolist(),
        }

        predictions[f"{aspect}_actual"] = [LABEL_ORDER[index] for index in actual_ids]
        predictions[f"{aspect}_predicted"] = [
            LABEL_ORDER[index] for index in predicted_ids
        ]
        predictions[f"{aspect}_confidence"] = probability.max(axis=1)
        for index, label in enumerate(LABEL_ORDER):
            predictions[f"{aspect}_{label.lower()}_probability"] = probability[:, index]

    metrics["average_accuracy"] = float(np.mean(accuracies))
    metrics["average_macro_f1"] = float(np.mean(macro_f1_values))
    metrics["test_rows"] = int(len(test))
    metrics["label_order"] = list(LABEL_ORDER)
    return metrics, predictions, matrices


def plot_training_history(history: pd.DataFrame, path: Path) -> None:
    aspects = [aspect for aspect in ASPECTS if f"{aspect}_accuracy" in history.columns]
    figure, axes = plt.subplots(2, 1, figsize=(11, 9))
    axes[0].plot(history.index + 1, history["loss"], label="train loss")
    axes[0].plot(history.index + 1, history["val_loss"], label="validation loss")
    axes[0].set_title("Multi-task ABSA loss")
    axes[0].set_xlabel("Epoch")
    axes[0].set_ylabel("Loss")
    axes[0].legend()
    axes[0].grid(alpha=0.25)

    for aspect in aspects:
        axes[1].plot(
            history.index + 1,
            history[f"val_{aspect}_accuracy"],
            label=f"{aspect} validation",
        )
    axes[1].set_title("Validation accuracy by aspect")
    axes[1].set_xlabel("Epoch")
    axes[1].set_ylabel("Accuracy")
    axes[1].set_ylim(0, 1)
    axes[1].legend()
    axes[1].grid(alpha=0.25)
    figure.tight_layout()
    figure.savefig(path, dpi=160)
    plt.close(figure)


def plot_confusion_matrices(matrices: dict[str, np.ndarray], path: Path) -> None:
    figure, axes = plt.subplots(2, 2, figsize=(12, 10))
    for axis, aspect in zip(axes.ravel(), ASPECTS, strict=True):
        matrix = matrices[aspect]
        image = axis.imshow(matrix, cmap="Blues")
        axis.set_title(aspect.title())
        axis.set_xlabel("Predicted")
        axis.set_ylabel("Actual")
        axis.set_xticks(range(len(LABEL_ORDER)), LABEL_ORDER, rotation=20)
        axis.set_yticks(range(len(LABEL_ORDER)), LABEL_ORDER)
        for row in range(matrix.shape[0]):
            for column in range(matrix.shape[1]):
                axis.text(column, row, str(matrix[row, column]), ha="center", va="center")
        figure.colorbar(image, ax=axis, fraction=0.046, pad=0.04)
    figure.suptitle("Component 4 ABSA confusion matrices")
    figure.tight_layout()
    figure.savefig(path, dpi=160)
    plt.close(figure)


def save_model_summary(model: keras.Model, path: Path) -> None:
    lines: list[str] = []
    model.summary(print_fn=lines.append)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def vocabulary_payload(
    vectorizer: layers.TextVectorization,
    config: TrainingConfig,
) -> dict[str, Any]:
    vocabulary = vectorizer.get_vocabulary()
    return {
        "version": PREPROCESSING_VERSION,
        "standardize": "component4>standardize_review_text",
        "split": "whitespace",
        "output_mode": "int",
        "max_tokens": config.max_tokens,
        "sequence_length": config.sequence_length,
        "vocabulary_size": len(vocabulary),
        "vocabulary": vocabulary,
    }


def train(
    reviews_path: Path,
    labels_path: Path,
    artifact_dir: Path,
    report_dir: Path,
    config: TrainingConfig,
) -> dict[str, Any]:
    set_reproducibility(config.seed)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)

    data = load_dataset(reviews_path, labels_path)
    train_frame, validation_frame, test_frame = split_dataset(data, config)
    vectorizer = build_vectorizer(train_frame["review_text"], config)
    model = build_model(vectorizer, config)

    train_dataset, class_weights = make_dataset(
        train_frame,
        config,
        training=True,
        include_sample_weights=True,
    )
    validation_dataset, _ = make_dataset(
        validation_frame,
        config,
        training=False,
    )
    test_dataset, _ = make_dataset(test_frame, config, training=False)

    model_path = artifact_dir / "absa_model.keras"
    callbacks = [
        keras.callbacks.EarlyStopping(
            monitor="val_loss",
            patience=config.early_stopping_patience,
            restore_best_weights=True,
            verbose=1,
        ),
        keras.callbacks.ReduceLROnPlateau(
            monitor="val_loss",
            factor=0.5,
            patience=config.reduce_lr_patience,
            min_lr=1e-5,
            verbose=1,
        ),
        keras.callbacks.ModelCheckpoint(
            model_path,
            monitor="val_loss",
            save_best_only=True,
            verbose=1,
        ),
        keras.callbacks.TerminateOnNaN(),
    ]

    history = model.fit(
        train_dataset,
        validation_data=validation_dataset,
        epochs=config.epochs,
        callbacks=callbacks,
        shuffle=False,
        verbose=2,
    )
    model.save(model_path)

    reloaded = keras.models.load_model(model_path, compile=False)
    predicted = reloaded.predict(test_dataset, verbose=0)
    require(isinstance(predicted, dict), "multi-task model prediction must be a mapping")
    metrics, predictions, matrices = evaluate_predictions(test_frame, predicted)

    history_frame = pd.DataFrame(history.history)
    best_epoch_index = int(history_frame["val_loss"].idxmin())
    metrics["training"] = {
        "epochs_requested": config.epochs,
        "epochs_completed": int(len(history_frame)),
        "best_epoch": best_epoch_index + 1,
        "best_validation_loss": float(history_frame.loc[best_epoch_index, "val_loss"]),
    }
    history_path = report_dir / "absa_training_history.csv"
    predictions_path = report_dir / "absa_test_predictions.csv"
    metrics_path = report_dir / "absa_metrics.json"
    training_curves_path = report_dir / "absa_training_curves.png"
    confusion_path = report_dir / "absa_confusion_matrices.png"
    summary_path = report_dir / "absa_model_summary.txt"

    history_frame.to_csv(history_path, index_label="epoch_index", lineterminator="\n")
    predictions.to_csv(predictions_path, index=False, lineterminator="\n")
    write_json(metrics_path, metrics)
    plot_training_history(history_frame, training_curves_path)
    plot_confusion_matrices(matrices, confusion_path)
    save_model_summary(reloaded, summary_path)

    vocabulary_path = artifact_dir / "text_vectorization_vocabulary.json"
    label_mapping_path = artifact_dir / "label_mapping.json"
    training_config_path = artifact_dir / "training_config.json"
    write_json(vocabulary_path, vocabulary_payload(vectorizer, config))
    write_json(
        label_mapping_path,
        {
            "version": LABEL_MAPPING_VERSION,
            "label_order": list(LABEL_ORDER),
            "label_to_id": LABEL_TO_ID,
            "aspect_output_names": list(ASPECTS),
            "aspect_label_columns": ASPECT_TO_LABEL_COLUMN,
        },
    )
    write_json(
        training_config_path,
        {
            **asdict(config),
            "model_version": MODEL_VERSION,
            "preprocessing_version": PREPROCESSING_VERSION,
            "class_weights": class_weights,
            "split_counts": {
                "train": len(train_frame),
                "validation": len(validation_frame),
                "test": len(test_frame),
            },
        },
    )

    manifest_path = artifact_dir / "manifest.json"
    manifest = {
        "model_version": MODEL_VERSION,
        "preprocessing_version": PREPROCESSING_VERSION,
        "label_mapping_version": LABEL_MAPPING_VERSION,
        "framework": {
            "tensorflow": tf.__version__,
            "keras": keras.__version__,
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
        "architecture": {
            "encoder": "Bidirectional LSTM",
            "attention": "MultiHeadAttention",
            "attention_heads": config.attention_heads,
            "attention_key_dim": config.attention_key_dim,
            "output_heads": list(ASPECTS),
            "classes_per_head": len(LABEL_ORDER),
        },
        "inputs": {
            "reviews": file_metadata(reviews_path),
            "labels": file_metadata(labels_path),
        },
        "artifacts": {
            "model": file_metadata(model_path),
            "vocabulary": file_metadata(vocabulary_path),
            "label_mapping": file_metadata(label_mapping_path),
            "training_config": file_metadata(training_config_path),
        },
        "reports": {
            "metrics": file_metadata(metrics_path),
            "history": file_metadata(history_path),
            "test_predictions": file_metadata(predictions_path),
            "training_curves": file_metadata(training_curves_path),
            "confusion_matrices": file_metadata(confusion_path),
            "model_summary": file_metadata(summary_path),
        },
        "metrics_summary": {
            "average_accuracy": metrics["average_accuracy"],
            "average_macro_f1": metrics["average_macro_f1"],
            **metrics["training"],
        },
        "smoke_test": config.smoke_test,
    }
    write_json(manifest_path, manifest)

    print("Component 4 Phase 3 ABSA training completed.")
    print(f"Model: {model_path}")
    print(f"Average accuracy: {metrics['average_accuracy']:.4f}")
    print(f"Average macro-F1: {metrics['average_macro_f1']:.4f}")
    print(f"Metrics: {metrics_path}")
    return manifest


def smoke_config(base: TrainingConfig) -> TrainingConfig:
    values = asdict(base)
    values.update(
        {
            "max_tokens": 2_000,
            "sequence_length": 48,
            "embedding_dim": 32,
            "lstm_units": 16,
            "attention_heads": 2,
            "attention_key_dim": 8,
            "dense_units": 24,
            "batch_size": 32,
            "epochs": 1,
            "max_train_samples": 512,
            "max_validation_samples": 128,
            "max_test_samples": 128,
            "smoke_test": True,
        }
    )
    return TrainingConfig(**values)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reviews", type=Path, default=DEFAULT_REVIEWS)
    parser.add_argument("--labels", type=Path, default=DEFAULT_LABELS)
    parser.add_argument("--artifact-dir", type=Path, default=DEFAULT_ARTIFACT_DIR)
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--smoke-test", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = TrainingConfig(epochs=args.epochs, batch_size=args.batch_size)
    if args.smoke_test:
        config = smoke_config(config)
    train(
        reviews_path=args.reviews.resolve(),
        labels_path=args.labels.resolve(),
        artifact_dir=args.artifact_dir.resolve(),
        report_dir=args.report_dir.resolve(),
        config=config,
    )


if __name__ == "__main__":
    main()
