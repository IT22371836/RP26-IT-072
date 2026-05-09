from __future__ import annotations

import json
import logging
import pickle
import re
from dataclasses import dataclass
from threading import Lock
from typing import Optional

import numpy as np

from .config import get_paths

logger = logging.getLogger(__name__)

_ADJ_SUFFIXES = re.compile(
    r'^(?:\w+(?:ful|less|ive|ous|al|ent|ic|able|ible|ary|ory|ish))$', re.IGNORECASE
)
_COMMON_ADJ = frozenset([
    'good', 'bad', 'great', 'excellent', 'poor', 'fast', 'slow', 'nice', 'awful',
    'terrible', 'horrible', 'amazing', 'fantastic', 'wonderful', 'cheap', 'expensive',
    'clean', 'dirty', 'quick', 'late', 'early', 'new', 'old', 'big', 'small', 'large',
    'tiny', 'best', 'worst', 'happy', 'sad', 'helpful', 'rude', 'friendly', 'professional',
])
_PRONOUNS = frozenset([
    'i', 'me', 'my', 'mine', 'myself', 'we', 'us', 'our', 'ours', 'ourselves',
    'you', 'your', 'yours', 'yourself', 'he', 'him', 'his', 'himself',
    'she', 'her', 'hers', 'herself', 'they', 'them', 'their', 'theirs', 'themselves',
])
_POS_WORDS = frozenset([
    'good', 'great', 'excellent', 'amazing', 'fantastic', 'wonderful', 'best',
    'nice', 'helpful', 'professional', 'clean', 'fast', 'quick', 'friendly',
])
_NEG_WORDS = frozenset([
    'bad', 'poor', 'terrible', 'horrible', 'awful', 'worst', 'slow', 'late',
    'dirty', 'rude', 'unprofessional',
])


def extract_linguistic_features(text: str, rating: Optional[float] = None) -> dict:
    words = text.strip().split()
    n = len(words) or 1
    lower_words = [w.lower().rstrip('.,!?;:') for w in words]

    unique_word_ratio = len(set(lower_words)) / n
    pronoun_count = sum(1 for w in lower_words if w in _PRONOUNS)
    adj_count = sum(
        1 for w in lower_words if w in _COMMON_ADJ or bool(_ADJ_SUFFIXES.match(w))
    )
    caps_ratio = sum(1 for w in words if w.isupper() and len(w) > 1) / n

    if rating is not None:
        pos = sum(1 for w in lower_words if w in _POS_WORDS)
        neg = sum(1 for w in lower_words if w in _NEG_WORDS)
        sentiment = (pos - neg) / n
        normalized_rating = (float(rating) - 1.0) / 4.0
        rating_text_mismatch = abs(normalized_rating - (sentiment + 1.0) / 2.0)
    else:
        rating_text_mismatch = 0.0

    return {
        'word_count': n,
        'unique_word_ratio': round(unique_word_ratio, 4),
        'pronoun_count': pronoun_count,
        'adj_density': round(adj_count / n, 4),
        'exclamation_count': text.count('!'),
        'caps_ratio': round(caps_ratio, 4),
        'rating_text_mismatch': round(rating_text_mismatch, 4),
    }


@dataclass
class FraudArtifacts:
    model: object
    scaler: object
    feature_names: list


class FraudDetectionService:
    def __init__(self) -> None:
        self._lock = Lock()
        self._loaded = False
        self._artifacts: Optional[FraudArtifacts] = None
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

    def _load_artifacts(self) -> FraudArtifacts:
        paths = self._paths
        if not paths.fraud_model_path.exists():
            raise FileNotFoundError(f"isolation_forest.pkl not found at {paths.fraud_model_path}")

        with open(paths.fraud_model_path, 'rb') as f:
            saved = pickle.load(f)

        if isinstance(saved, dict):
            model = saved['model']
            scaler = saved.get('scaler')
        else:
            model = saved
            scaler = None

        feature_names: list = []
        if paths.blend_config_path.exists():
            with open(paths.blend_config_path) as f:
                blend_cfg = json.load(f)
            feature_names = blend_cfg.get('feature_names', [])

        logger.info("Fraud detection model loaded")
        return FraudArtifacts(model=model, scaler=scaler, feature_names=feature_names)

    def score_review(
        self,
        text: str,
        rating: Optional[float] = None,
        user_total_reviews: int = 5,
        days_since_prev_review: float = 30.0,
        user_provider_diversity: float = 3.0,
        text_frequency: int = 1,
        days_since_review: float = 30.0,
        booking_status: int = 1,
    ) -> dict:
        self.ensure_loaded()
        arts = self._artifacts

        ling = extract_linguistic_features(text, rating)
        behavioral = {
            'user_total_reviews': float(user_total_reviews),
            'days_since_prev_review': float(days_since_prev_review),
            'user_provider_diversity': float(user_provider_diversity),
            'text_frequency': float(text_frequency),
            'days_since_review': float(days_since_review),
            'booking_status': float(booking_status),
        }
        feature_dict = {**ling, **behavioral}

        feature_names = arts.feature_names or list(feature_dict.keys())
        X = np.array([[feature_dict.get(fn, 0.0) for fn in feature_names]], dtype=np.float64)

        if arts.scaler is not None:
            X = arts.scaler.transform(X)

        pred = int(arts.model.predict(X)[0])
        raw_score = float(arts.model.score_samples(X)[0])
        # score_samples: higher (less negative) = more normal; invert to fraud_score [0, 1]
        fraud_score = max(0.0, min(1.0, -raw_score / 0.8))

        if pred == -1:
            trust_label = 'Suspicious'
        elif fraud_score < 0.35:
            trust_label = 'Verified'
        else:
            trust_label = 'Unverified'

        return {
            'fraud_score': round(fraud_score, 4),
            'trust_label': trust_label,
            'is_suspicious': pred == -1,
            'linguistic_features': ling,
        }


_fraud_service: FraudDetectionService | None = None
_fraud_lock = Lock()


def get_fraud_detection_service() -> FraudDetectionService:
    global _fraud_service
    if _fraud_service is None:
        with _fraud_lock:
            if _fraud_service is None:
                _fraud_service = FraudDetectionService()
    return _fraud_service
