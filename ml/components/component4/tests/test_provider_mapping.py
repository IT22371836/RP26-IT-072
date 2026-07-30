from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest


SOURCE_DIR = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SOURCE_DIR))

import category_prior  # noqa: E402
import map_providers  # noqa: E402


def source_provider_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "provider_id": ["C4-B", "C4-A", "C4-C"],
            "service_type": ["Plumbers", "Plumbers", "A/C"],
            "district": ["Galle", "Colombo", "Kandy"],
            "total_reviews": [2, 0, 3],
            "trust_sentiment_score": [0.8, 0.0, 0.6],
        }
    )


def component1_provider_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "provider_id": ["P00003", "P00001", "P00002", "P00004", "P00005"],
            "provider_name": ["C", "A", "B", "D", "E"],
            "category": ["Plumbers", "Plumbers", "Plumbers", "A/C", "A/C"],
            "district": ["Kandy", "Colombo", "Galle", "Kandy", "Galle"],
        }
    )


def test_mapping_is_deterministic_and_independent_of_input_order() -> None:
    sources = source_provider_frame()
    targets = component1_provider_frame()

    first = map_providers.build_provider_mapping(sources, targets)
    second = map_providers.build_provider_mapping(
        sources.sample(frac=1, random_state=7),
        targets.sample(frac=1, random_state=9),
    )

    pd.testing.assert_frame_equal(first, second)
    assert dict(zip(first["source_provider_id"], first["provider_id"], strict=True)) == {
        "C4-A": "P00001",
        "C4-B": "P00002",
        "C4-C": "P00004",
    }


def test_mapping_is_category_consistent_unique_and_complete() -> None:
    mapping = map_providers.build_provider_mapping(
        source_provider_frame(), component1_provider_frame()
    )

    assert len(mapping) == 3
    assert mapping["source_provider_id"].is_unique
    assert mapping["provider_id"].is_unique
    assert mapping["source_category"].equals(mapping["category"])


def test_mapping_rejects_a_category_with_insufficient_targets() -> None:
    sources = source_provider_frame()
    targets = component1_provider_frame().query(
        "provider_id not in ['P00002', 'P00003']"
    )

    with pytest.raises(map_providers.ProviderMappingError, match="only 1 C1 targets"):
        map_providers.build_provider_mapping(sources, targets)


def test_mapped_reviews_preserve_source_ids_and_review_fields() -> None:
    mapping = map_providers.build_provider_mapping(
        source_provider_frame(), component1_provider_frame()
    )
    reviews = pd.DataFrame(
        {
            "review_id": ["R1", "R2"],
            "provider_id": ["C4-A", "C4-B"],
            "service_type": ["Plumbers", "Plumbers"],
            "rating": [5, 2],
            "review_text": ["Excellent work", "Arrived late"],
        }
    )

    mapped, unmapped = map_providers.map_reviews(reviews, mapping)

    assert unmapped == 0
    assert mapped["source_provider_id"].tolist() == ["C4-A", "C4-B"]
    assert mapped["provider_id"].tolist() == ["P00001", "P00002"]
    assert mapped["review_text"].equals(reviews["review_text"])
    assert mapped["rating"].equals(reviews["rating"])


def test_frozen_mapping_rejects_a_changed_assignment(tmp_path: Path) -> None:
    mapping = map_providers.build_provider_mapping(
        source_provider_frame(), component1_provider_frame()
    )
    path = tmp_path / "provider_id_map.csv"
    map_providers.freeze_mapping(path, mapping)

    changed = mapping.copy()
    changed.loc[0, "provider_id"] = "P99999"
    with pytest.raises(map_providers.ProviderMappingError, match="differs from the frozen"):
        map_providers.freeze_mapping(path, changed)


def test_category_prior_fallback_has_zero_evidence() -> None:
    priors = map_providers.build_category_priors(source_provider_frame())
    fallback = category_prior.build_no_review_fallback("P99999", "Plumbers", priors)

    assert fallback["final_score"] == 0.8
    assert fallback["effective_review_count"] == 0.0
    assert fallback["reliability_factor"] == 0.0
    assert fallback["evidence_status"] == "insufficient"
    assert fallback["score_source"] == "category_prior"
    assert all(value == 0.0 for value in fallback["aspect_scores"].values())
