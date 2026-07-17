import importlib.util
from pathlib import Path
from types import ModuleType

import numpy as np
import pandas as pd
import pytest


def load_exporter_module() -> ModuleType:
    repository_root = Path(__file__).resolve().parents[4]
    exporter_path = (
        repository_root / "ml" / "components" / "component1" / "src" / "export_artifacts.py"
    )
    spec = importlib.util.spec_from_file_location("component1_export_artifacts", exporter_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load the Component 1 artifact exporter")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


exporter = load_exporter_module()


def test_exporter_normalizes_scores_and_handles_constant_input() -> None:
    assert exporter.normalize(np.array([1.0, 2.0, 3.0])).tolist() == [0.0, 0.5, 1.0]
    assert exporter.normalize(np.array([4.0, 4.0])).tolist() == [0.5, 0.5]


def test_exporter_rejects_provider_dataset_with_missing_columns(tmp_path: Path) -> None:
    provider_path = tmp_path / "providers.json"
    interaction_path = tmp_path / "interactions.csv"
    pd.DataFrame([{"provider_id": "P001"}]).to_json(provider_path, orient="records")
    pd.DataFrame(
        [
            {
                "interaction_id": "I001",
                "user_id": "U001",
                "provider_id": "P001",
                "rating": 5,
                "booking_status": "completed",
            }
        ]
    ).to_csv(interaction_path, index=False)

    with pytest.raises(ValueError, match="Provider dataset is missing columns"):
        exporter.load_and_prepare(provider_path, interaction_path)
