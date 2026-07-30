from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pandas as pd
import pytest


COMPONENT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = COMPONENT_ROOT / "src"
REPOSITORY_ROOT = COMPONENT_ROOT.parents[2]
sys.path.insert(0, str(SRC_ROOT))

from evaluate_ranking import (  # noqa: E402
    METHODS,
    binary_top_k_metrics,
    build_candidate_queries,
    build_proxy_ground_truth,
    dcg_at_k,
    ndcg_at_k,
)


ARTIFACT_DIR = COMPONENT_ROOT / "artifacts" / "evaluation-v1"
REPORT_DIR = COMPONENT_ROOT / "reports" / "evaluation-v1"
MANIFEST = ARTIFACT_DIR / "manifest.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def test_ranking_metrics_reward_the_ideal_order() -> None:
    ideal = [1.0, 0.8, 0.6, 0.4, 0.2]
    reversed_order = list(reversed(ideal))

    assert dcg_at_k(ideal, 5) > dcg_at_k(reversed_order, 5)
    assert ndcg_at_k(ideal, ideal, 5) == pytest.approx(1.0)
    assert 0 < ndcg_at_k(reversed_order, ideal, 5) < 1

    precision, recall, average_precision = binary_top_k_metrics(
        ["P1", "P6", "P2", "P7", "P3"],
        ["P1", "P2", "P3", "P4", "P5"],
        5,
    )
    assert precision == pytest.approx(0.6)
    assert recall == pytest.approx(0.6)
    assert average_precision == pytest.approx((1 + 2 / 3 + 3 / 5) / 5)


def test_proxy_ground_truth_uses_only_heldout_rating_and_actual_credibility() -> None:
    reviews = pd.DataFrame(
        [
            {
                "review_id": "R-TRAIN",
                "provider_id": "P1",
                "service_type": "Plumbers",
                "dataset_split": "train",
                "rating": 1,
            },
            {
                "review_id": "R-TEST-1",
                "provider_id": "P1",
                "service_type": "Plumbers",
                "dataset_split": "test",
                "rating": 5,
            },
            {
                "review_id": "R-TEST-2",
                "provider_id": "P1",
                "service_type": "Plumbers",
                "dataset_split": "test",
                "rating": 4,
            },
        ]
    )
    credibility = pd.DataFrame(
        [
            {"review_id": "R-TRAIN", "credibility_score": 1.0, "is_fake_review": 0},
            {"review_id": "R-TEST-1", "credibility_score": 0.5, "is_fake_review": 1},
            {"review_id": "R-TEST-2", "credibility_score": 1.0, "is_fake_review": 0},
        ]
    )

    proxy = build_proxy_ground_truth(reviews, credibility)

    assert len(proxy) == 1
    assert proxy.iloc[0]["test_review_count"] == 2
    assert proxy.iloc[0]["proxy_relevance"] == pytest.approx((0.5 + 0.8) / 2)


def test_candidate_fixtures_are_deterministic_category_consistent_and_cover_all() -> None:
    proxy = pd.DataFrame(
        [
            {
                "provider_id": f"P{index:03d}",
                "category": "Plumbers",
                "proxy_relevance": index / 25,
                "test_review_count": 1,
            }
            for index in range(23)
        ]
    )

    first = build_candidate_queries(proxy, seed="fixed-seed")
    second = build_candidate_queries(
        proxy.sample(frac=1, random_state=7).reset_index(drop=True),
        seed="fixed-seed",
    )

    pd.testing.assert_frame_equal(first, second)
    assert first["query_id"].nunique() == 3
    assert first.groupby("query_id").size().eq(10).all()
    assert first.groupby("query_id")["category"].nunique().eq(1).all()
    assert first["is_supplement"].sum() == 7
    assert set(first.loc[~first["is_supplement"], "provider_id"]) == set(
        proxy["provider_id"]
    )


def test_phase8_artifacts_have_auditable_scope_and_complete_metrics() -> None:
    audit = json.loads(
        (REPORT_DIR / "ranking_evaluation.json").read_text(encoding="utf-8")
    )
    method_metrics = pd.read_csv(REPORT_DIR / "method_metrics.csv")
    category_metrics = pd.read_csv(REPORT_DIR / "category_metrics.csv")
    queries = pd.read_csv(REPORT_DIR / "evaluation_queries.csv")

    assert audit["status"] == "passed"
    assert audit["validation_scope"] == "held_out_proxy_not_production_ground_truth"
    assert audit["summary"]["total_reviews"] == 25_000
    assert audit["summary"]["ranking_evidence_reviews"] == 21_004
    assert audit["summary"]["heldout_proxy_reviews"] == 3_996
    assert audit["summary"]["split_overlap_records"] == 0
    assert audit["summary"]["category_mismatches"] == 0
    assert audit["summary"]["unique_candidate_providers"] == 2_731
    assert audit["candidate_source"] == "deterministic_category_fixture_not_component2"
    assert audit["proxy_definition"]["production_ground_truth"] is False
    assert set(method_metrics["method"]) == set(METHODS)
    assert len(category_metrics) == 14 * len(METHODS)
    assert queries.groupby("query_id").size().eq(10).all()
    assert queries.groupby("query_id")["category"].nunique().eq(1).all()
    for metric in ("ndcg_at_5", "precision_at_5", "recall_at_5", "map_at_5"):
        assert method_metrics[metric].between(0, 1).all()


def test_phase8_manifest_hashes_every_input_artifact_and_report() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["evaluation_version"] == "ranking-evaluation-v1"
    assert manifest["status"] == "passed"

    checked = 0
    for section in ("inputs", "artifacts", "reports"):
        for metadata in manifest[section].values():
            path = REPOSITORY_ROOT / metadata["path"]
            assert path.is_file()
            assert path.stat().st_size == metadata["bytes"]
            assert sha256_file(path) == metadata["sha256"]
            checked += 1

    assert checked == 16
