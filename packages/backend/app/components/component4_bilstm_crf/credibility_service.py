from __future__ import annotations

import json
import logging
from threading import Lock
from typing import Optional

from .config import get_paths

logger = logging.getLogger(__name__)


def _provider_scores_csv_candidates(paths) -> list:
    repo_root = paths.model_dir.parents[5] if len(paths.model_dir.parents) > 5 else paths.model_dir.parent
    return [
        paths.provider_scores_path.with_suffix('.csv'),
        repo_root / 'Component4 new' / 'component4_model' / 'provider_scores.csv',
        repo_root / 'Component4' / 'component4_model' / 'provider_scores.csv',
    ]


class CredibilityService:
    def __init__(self) -> None:
        self._lock = Lock()
        self._loaded = False
        self._df = None
        self._blend_cfg: dict = {}
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
            self._load_artifacts()
            self._loaded = True

    def _load_artifacts(self) -> None:
        import pandas as pd

        paths = self._paths
        csv_candidates = _provider_scores_csv_candidates(paths)

        def _read_csv_fallback() -> object:
            for candidate in csv_candidates:
                if candidate.exists():
                    return pd.read_csv(str(candidate))
            return None

        if not paths.provider_scores_path.exists():
            df = _read_csv_fallback()
            if df is None:
                raise FileNotFoundError(
                    f"provider_scores.parquet not found at {paths.provider_scores_path}"
                )
        if not paths.blend_config_path.exists():
            raise FileNotFoundError(
                f"blend_config.json not found at {paths.blend_config_path}"
            )

        if 'df' not in locals():
            try:
                df = pd.read_parquet(str(paths.provider_scores_path))
            except ImportError as exc:
                # Parquet engine not available (pyarrow/fastparquet). Try CSV fallbacks.
                df = _read_csv_fallback()
                if df is None:
                    raise RuntimeError(
                        "Parquet support is not available (install 'pyarrow' or 'fastparquet'), "
                        f"or provide a CSV at one of: {', '.join(str(p) for p in csv_candidates)}"
                    ) from exc
        if 'provider_id' in df.columns:
            df['provider_id'] = df['provider_id'].astype(str)
            df = df.set_index('provider_id')

        self._df = df

        with open(paths.blend_config_path) as f:
            self._blend_cfg = json.load(f)

        logger.info("Credibility service loaded: %d provider scores", len(df))

    def _assign_tier(self, s_final: float) -> str:
        thresholds = self._blend_cfg.get(
            'tier_thresholds', {'Elite': 0.8, 'Trusted': 0.65, 'Verified': 0.0}
        )
        if s_final >= thresholds.get('Elite', 0.8):
            return 'Elite'
        if s_final >= thresholds.get('Trusted', 0.65):
            return 'Trusted'
        return 'Verified'

    @staticmethod
    def _generate_explanation(data: dict) -> str:
        s_cred = data.get('S_cred')
        s_overall = data.get('S_overall')
        fraud_ratio = data.get('fraud_ratio') or 0.0
        recency_boost = data.get('recency_boost') or 0.0
        total_reviews = data.get('total_reviews') or 0

        if s_cred is not None:
            if s_cred >= 0.75:
                cred_str = "highly credible credentials and experience"
            elif s_cred >= 0.5:
                cred_str = "moderate credentials and experience"
            else:
                cred_str = "limited verifiable credentials"
        else:
            cred_str = "credentials not evaluated"

        if s_overall is not None:
            if s_overall >= 0.75:
                overall_str = "customers consistently rate the service highly"
            elif s_overall >= 0.5:
                overall_str = "customer ratings are generally positive"
            else:
                overall_str = "customer ratings show mixed feedback"
        else:
            overall_str = "customer ratings not available"

        if fraud_ratio <= 0.05:
            fraud_str = "reviews appear genuine"
        elif fraud_ratio <= 0.20:
            fraud_str = f"{fraud_ratio * 100:.0f}% of reviews flagged as suspicious"
        else:
            fraud_str = f"high fraud rate ({fraud_ratio * 100:.0f}% suspicious) — caution advised"

        recency_str = (
            "Recent activity is strong." if recency_boost >= 0.4
            else "Recent activity is moderate." if recency_boost >= 0.15
            else "Activity is dated."
        )

        review_str = (
            f"Based on {total_reviews} review{'s' if total_reviews != 1 else ''}."
            if total_reviews > 0 else ""
        )

        parts = [
            f"Provider has {cred_str}; {overall_str}.",
            f"{fraud_str.capitalize()}.",
            recency_str,
        ]
        if review_str:
            parts.append(review_str)
        return " ".join(parts)

    def get_provider_credibility(self, provider_id: str) -> Optional[dict]:
        self.ensure_loaded()
        pid = str(provider_id)
        if pid not in self._df.index:
            return None

        row = self._df.loc[pid]
        s_final = float(row.get('S_final', 0.0))
        result: dict = {
            'provider_id': pid,
            'S_final': round(s_final, 4),
            'tier': self._assign_tier(s_final),
        }
        for col in ('S_cred', 'S_overall', 'fraud_ratio', 'recency_boost', 'avg_rating'):
            if col in row.index:
                val = row[col]
                result[col] = round(float(val), 4) if val is not None else None
        for col in ('total_reviews', 'suspicious_count'):
            if col in row.index:
                val = row[col]
                result[col] = int(float(val)) if val is not None else None

        result['explanation'] = self._generate_explanation(result)
        return result

    def rank_providers(self, provider_ids: list[str]) -> list[dict]:
        self.ensure_loaded()
        known, unknown = [], []
        for pid in provider_ids:
            cred = self.get_provider_credibility(pid)
            if cred:
                known.append(cred)
            else:
                unknown.append({
                    'provider_id': str(pid), 'S_final': None, 'tier': 'Unknown',
                    'explanation': 'Provider not found in the credibility index.',
                })

        known.sort(key=lambda x: x['S_final'], reverse=True)
        ranked = []
        for rank, entry in enumerate(known + unknown, 1):
            entry['rank'] = rank
            ranked.append(entry)
        return ranked

    def get_random_providers(self, n: int = 8) -> list[str]:
        """Sample n random provider IDs from the pre-computed index."""
        self.ensure_loaded()
        sample = self._df.sample(min(n, len(self._df)), random_state=None)
        return sample.index.tolist()

    def run_pipeline(
        self,
        provider_ids: Optional[list[str]] = None,
        top_n: int = 5,
    ) -> dict:
        """
        Component 3 → Component 4 pipeline.
        If provider_ids is None, randomly samples 8 providers.
        Returns top_n ranked by S_final with full breakdown + explanation.
        """
        self.ensure_loaded()

        if provider_ids:
            source = "component3"
            note = (
                f"Received {len(provider_ids)} provider IDs from Component 3. "
                f"Ranked by S_final and returning Top-{top_n}."
            )
        else:
            provider_ids = self.get_random_providers(n=8)
            source = "random"
            note = (
                "Component 3 is not yet integrated. "
                f"Randomly sampled {len(provider_ids)} providers from the pre-computed index "
                f"and returning Top-{top_n} by S_final."
            )

        ranked = self.rank_providers(provider_ids)
        top = [r for r in ranked if r.get('tier') != 'Unknown'][:top_n]

        # Pad with unknowns only if we have fewer than top_n known providers
        if len(top) < top_n:
            unknowns = [r for r in ranked if r.get('tier') == 'Unknown']
            top += unknowns[: top_n - len(top)]

        return {
            'source': source,
            'providers_evaluated': len(provider_ids),
            'top_n': top_n,
            'ranked': top,
            'note': note,
        }

    @property
    def total_providers(self) -> int:
        if self._df is not None:
            return len(self._df)
        return 0


_credibility_service: CredibilityService | None = None
_credibility_lock = Lock()


def get_credibility_service() -> CredibilityService:
    global _credibility_service
    if _credibility_service is None:
        with _credibility_lock:
            if _credibility_service is None:
                _credibility_service = CredibilityService()
    return _credibility_service
