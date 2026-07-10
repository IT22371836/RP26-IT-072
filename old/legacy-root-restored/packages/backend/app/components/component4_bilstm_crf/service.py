from __future__ import annotations

import json
import logging
import pickle
from dataclasses import dataclass
from threading import Lock
from typing import Optional

import numpy as np

from .config import get_paths

logger = logging.getLogger(__name__)

# Lazy TF imports — only resolved when the service is first loaded
_tf = None
_keras = None
_pad_sequences = None


def _import_tf():
    global _tf, _keras, _pad_sequences
    if _tf is not None:
        return
    import tensorflow as tf
    from tensorflow import keras
    from tensorflow.keras.preprocessing.sequence import pad_sequences as _ps

    _tf = tf
    _keras = keras
    _pad_sequences = _ps


# ─── Pure-TensorFlow CRF (no tensorflow-addons) ───────────────────────────────

def _viterbi_np(score: np.ndarray, transition_params: np.ndarray):
    trellis = np.zeros_like(score)
    backpointers = np.zeros_like(score, dtype=np.int32)
    trellis[0] = score[0]
    for t in range(1, score.shape[0]):
        v = trellis[t - 1][:, None] + transition_params
        trellis[t] = score[t] + np.max(v, axis=0)
        backpointers[t] = np.argmax(v, axis=0)
    path = [int(np.argmax(trellis[-1]))]
    for bp in reversed(backpointers[1:]):
        path.append(int(bp[path[-1]]))
    path.reverse()
    return path, float(np.max(trellis[-1]))


def _build_crf_layer_class():
    """Build CRFLayer class after TF is imported."""
    tf = _tf
    keras = _keras

    class CRFLayer(keras.layers.Layer):
        def __init__(self, num_tags, **kwargs):
            super().__init__(**kwargs)
            self.num_tags = num_tags

        def build(self, input_shape):
            self.transition_params = self.add_weight(
                shape=(self.num_tags, self.num_tags),
                name="transitions",
                initializer="glorot_uniform",
                trainable=True,
            )
            self.built = True

        def call(self, inputs):
            return inputs

        def crf_log_likelihood(self, inputs, tag_indices, sequence_lengths):
            max_len = tf.shape(inputs)[1]
            mask = tf.sequence_mask(sequence_lengths, max_len, tf.float32)

            unary = tf.reduce_sum(
                tf.reduce_sum(inputs * tf.one_hot(tag_indices, self.num_tags), -1) * mask,
                1,
            )
            t1 = tf.cast(tag_indices[:, :-1], tf.int32)
            t2 = tf.cast(tag_indices[:, 1:], tf.int32)
            flat_trans = tf.reshape(self.transition_params, [-1])
            trans = tf.reduce_sum(
                tf.gather(flat_trans, t1 * self.num_tags + t2) * mask[:, 1:], 1
            )
            log_Z = self._log_partition(inputs, sequence_lengths)
            return unary + trans - log_Z, self.transition_params

        def _log_partition(self, inputs, sequence_lengths):
            max_len = tf.shape(inputs)[1]
            alphas = inputs[:, 0, :]
            trans = tf.expand_dims(self.transition_params, 0)
            for t in tf.range(1, max_len):
                new_a = (
                    tf.reduce_logsumexp(tf.expand_dims(alphas, 2) + trans, 1)
                    + inputs[:, t, :]
                )
                active = tf.cast(t < sequence_lengths, tf.float32)[:, None]
                alphas = new_a * active + alphas * (1.0 - active)
            return tf.reduce_logsumexp(alphas, 1)

        def viterbi_decode_batch(self, inputs, sequence_lengths):
            inp = inputs.numpy()
            lens = sequence_lengths.numpy()
            tr = self.transition_params.numpy()
            ml = inp.shape[1]
            results = []
            for b in range(inp.shape[0]):
                path, _ = _viterbi_np(inp[b, : int(lens[b])], tr)
                results.append(path + [0] * (ml - len(path)))
            return tf.constant(results, dtype=tf.int32)

        def get_config(self):
            cfg = super().get_config()
            cfg["num_tags"] = self.num_tags
            return cfg

    return CRFLayer


def _build_model_class():
    """Build BiLSTMCRF class after TF is imported."""
    keras = _keras
    layers = _keras.layers

    CRFLayer = _build_crf_layer_class()

    class BiLSTMCRF(keras.Model):
        def __init__(
            self,
            vocab_size,
            embedding_dim,
            lstm_units,
            num_tags,
            dropout_rate,
            recurrent_dropout,
        ):
            super().__init__()
            self.num_tags = num_tags
            self.embedding = layers.Embedding(
                vocab_size, embedding_dim, mask_zero=True, name="embedding"
            )
            self.spatial_dropout = layers.SpatialDropout1D(dropout_rate)
            self.bilstm = layers.Bidirectional(
                layers.LSTM(
                    lstm_units,
                    return_sequences=True,
                    dropout=dropout_rate,
                    recurrent_dropout=recurrent_dropout,
                ),
                name="bi_lstm",
            )
            self.dense = layers.Dense(num_tags, name="logits")
            self.crf = CRFLayer(num_tags, name="crf")
            self.crf.build((None, None, num_tags))

        def call(self, inputs, training=False):
            x = self.embedding(inputs)
            x = self.spatial_dropout(x, training=training)
            x = self.bilstm(x, training=training)
            return self.dense(x)

        def decode(self, logits, sequence_lengths):
            return self.crf.viterbi_decode_batch(logits, sequence_lengths)

    return BiLSTMCRF


# ─── Artifacts & Service ──────────────────────────────────────────────────────

@dataclass
class Component4Artifacts:
    model: object          # BiLSTMCRF instance
    word2idx: dict
    tag2idx: dict
    idx2tag: dict
    max_len: int
    model_config: dict


class BiLSTMCRFService:
    def __init__(self) -> None:
        self._lock = Lock()
        self._loaded = False
        self._artifacts: Optional[Component4Artifacts] = None
        self._paths = get_paths()

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def ensure_loaded(self) -> None:
        if self._loaded:
            return
        with self._lock:
            if self._loaded:
                return
            self._artifacts = self._load_artifacts()
            self._loaded = True

    def _load_artifacts(self) -> Component4Artifacts:
        paths = self._paths

        if not paths.vocab_path.exists():
            raise FileNotFoundError(f"vocab.pkl not found at {paths.vocab_path}")
        if not paths.config_path.exists():
            raise FileNotFoundError(f"model_config.json not found at {paths.config_path}")
        if not paths.weights_path.exists():
            raise FileNotFoundError(
                f"Model weights not found at {paths.weights_path}"
            )

        _import_tf()
        tf = _tf

        with open(paths.vocab_path, "rb") as f:
            vocab = pickle.load(f)

        with open(paths.config_path) as f:
            cfg = json.load(f)

        BiLSTMCRF = _build_model_class()
        model = BiLSTMCRF(
            vocab_size=cfg["vocab_size"],
            embedding_dim=cfg["embedding_dim"],
            lstm_units=cfg["lstm_units"],
            num_tags=cfg["num_tags"],
            dropout_rate=cfg["dropout_rate"],
            recurrent_dropout=cfg["recurrent_dropout"],
        )
        # Warm-up pass to build weights before loading
        _ = model(tf.zeros((1, cfg["max_len"]), tf.int32))
        model.load_weights(str(paths.weights_path))

        logger.info("Component 4 BiLSTM-CRF model loaded (macro F1=%.4f)", cfg.get("macro_f1", 0))

        return Component4Artifacts(
            model=model,
            word2idx=vocab["word2idx"],
            tag2idx=vocab["tag2idx"],
            idx2tag=vocab["idx2tag"],
            max_len=vocab["MAX_LEN"],
            model_config=cfg,
        )

    def analyze(self, text: str) -> dict:
        self.ensure_loaded()
        tf = _tf
        artifacts = self._require_artifacts()

        tokens = text.strip().split()
        if not tokens:
            raise ValueError("text must contain at least one token")

        token_ids = [artifacts.word2idx.get(t.lower(), 1) for t in tokens]
        padded = _pad_sequences([token_ids], maxlen=artifacts.max_len, padding="post", value=0)
        length = np.array([min(len(tokens), artifacts.max_len)], dtype=np.int32)

        logits = artifacts.model(tf.cast(padded, tf.int32), training=False)
        decoded = artifacts.model.decode(logits, tf.cast(length, tf.int32))
        eff_len = int(length[0])
        tags = [artifacts.idx2tag[i] for i in decoded.numpy()[0][:eff_len]]

        probs = tf.nn.softmax(logits[0], axis=-1).numpy()[:eff_len]
        asp_map = {
            "QUAL": ("B-QUAL", "I-QUAL"),
            "PRICE": ("B-PRICE", "I-PRICE"),
            "TIME": ("B-TIME", "I-TIME"),
            "COMM": ("B-COMM", "I-COMM"),
        }
        aspect_scores: dict = {}
        for asp, asp_tags in asp_map.items():
            asp_probs = [
                sum(probs[j][artifacts.tag2idx[t]] for t in asp_tags if t in artifacts.tag2idx)
                for j, tag in enumerate(tags)
                if tag in asp_tags
            ]
            aspect_scores[asp] = float(np.mean(asp_probs)) if asp_probs else None

        return {
            "tokens": [{"token": tok, "tag": tag} for tok, tag in zip(tokens[:eff_len], tags)],
            "aspects": aspect_scores,
        }

    def _require_artifacts(self) -> Component4Artifacts:
        self.ensure_loaded()
        if self._artifacts is None:
            raise RuntimeError("Component 4 artifacts are not loaded")
        return self._artifacts


_service: BiLSTMCRFService | None = None
_service_lock = Lock()


def get_bilstm_crf_service() -> BiLSTMCRFService:
    global _service
    if _service is None:
        with _service_lock:
            if _service is None:
                _service = BiLSTMCRFService()
    return _service
