from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent


def _find_repo_root(start_dir: Path) -> Path:
    current = start_dir
    for _ in range(8):
        if (current / "packages").exists():
            return current
        if current.parent == current:
            break
        current = current.parent
    return start_dir


def _resolve_model_dir() -> Path:
    env_value = os.getenv("COMPONENT4_MODEL_DIR")
    if env_value:
        return Path(env_value)

    # Primary: model/ folder co-located with this component
    local_dir = BASE_DIR / "model"
    if local_dir.exists():
        return local_dir

    # Fallback: legacy Component4/ resource folder at repo root
    repo_root = _find_repo_root(BASE_DIR)
    return repo_root / "Component4" / "component4_model"


@dataclass(frozen=True)
class Component4Paths:
    model_dir: Path
    weights_path: Path
    config_path: Path
    vocab_path: Path


def get_paths() -> Component4Paths:
    model_dir = _resolve_model_dir()
    return Component4Paths(
        model_dir=model_dir,
        weights_path=Path(
            os.getenv("COMPONENT4_WEIGHTS", str(model_dir / "bilstm_crf_final.weights.h5"))
        ),
        config_path=Path(
            os.getenv("COMPONENT4_CONFIG", str(model_dir / "model_config.json"))
        ),
        vocab_path=Path(
            os.getenv("COMPONENT4_VOCAB", str(model_dir / "vocab.pkl"))
        ),
    )
