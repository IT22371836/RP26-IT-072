import hashlib
import json
from pathlib import Path

import pytest

from app.components.component4.service import Component4RankingEngine
from app.core.config import Settings
from scripts.validate_component4_release import (
    build_payloads,
    percentile,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
REPORT_DIR = (
    REPOSITORY_ROOT
    / "ml"
    / "components"
    / "component4"
    / "reports"
    / "release-v1"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def test_percentile_interpolates_deterministically() -> None:
    assert percentile([4, 1, 3, 2], 0) == 1
    assert percentile([4, 1, 3, 2], 0.5) == pytest.approx(2.5)
    assert percentile([4, 1, 3, 2], 1) == 4


def test_release_payloads_preserve_top10_to_top5_contract() -> None:
    settings = Settings()
    engine = Component4RankingEngine(
        settings.component4_artifact_dir,
        settings.component4_category_priors_path,
    )
    engine.load()
    payloads = build_payloads(
        sorted(engine.provider_scores),
        request_count=100,
        candidate_count=10,
        top_k=5,
        stride=7,
    )

    assert len(payloads) == 100
    assert all(len(payload.provider_ids) == 10 for payload in payloads)
    assert all(payload.top_k == 5 for payload in payloads)
    assert len({payload.request_id for payload in payloads}) == 100


def test_release_report_is_passed_but_keeps_external_gates_explicit() -> None:
    report = json.loads(
        (REPORT_DIR / "release_readiness.json").read_text(encoding="utf-8")
    )

    assert report["phase"] == 10
    assert report["status"] == "passed"
    assert report["component4_operationally_ready"] is True
    assert report["component2_connected"] is False
    assert report["production_ready"] is False
    assert report["benchmark"]["ranking_failures"] == 0
    assert all(report["checks"].values())
    assert "real Component 2 Top-10 API adapter" in report["remaining_production_gates"]


def test_release_manifest_hashes_inputs_and_report() -> None:
    manifest = json.loads((REPORT_DIR / "manifest.json").read_text(encoding="utf-8"))

    checked = 0
    for section in ("inputs", "reports"):
        for metadata in manifest[section].values():
            path = REPOSITORY_ROOT / metadata["path"]
            assert path.is_file()
            assert path.stat().st_size == metadata["bytes"]
            assert sha256_file(path) == metadata["sha256"]
            checked += 1

    assert checked == 4
