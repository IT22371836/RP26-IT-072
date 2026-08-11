from __future__ import annotations

import csv
from pathlib import Path

import pytest

from scripts.import_component4_research_reviews import (
    SEED_VERSION,
    compatible_marker,
    iter_write_entries,
    load_seed_data,
    research_customer_id,
)


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_research_customer_id_is_generated_without_impersonating_auth_user() -> None:
    assert research_customer_id("u34114") == "RCU34114"
    with pytest.raises(ValueError, match="Unsupported research user ID"):
        research_customer_id("real-firebase-uid")


def test_seed_data_preserves_review_identity_and_credibility(tmp_path: Path) -> None:
    provider_map = tmp_path / "provider_id_map.csv"
    credibility = tmp_path / "review_credibility_25k.csv"
    reviews = tmp_path / "customer_reviews_25k.csv"
    _write_csv(
        provider_map,
        ["source_provider_id", "provider_id"],
        [{"source_provider_id": "SP1", "provider_id": "P00001"}],
    )
    _write_csv(
        credibility,
        ["review_id", "is_fake_review", "credibility_score"],
        [
            {"review_id": "R1", "is_fake_review": "0", "credibility_score": "0.9"},
            {"review_id": "R2", "is_fake_review": "1", "credibility_score": "0.1"},
        ],
    )
    _write_csv(
        reviews,
        [
            "review_id",
            "booking_id",
            "user_id",
            "provider_id",
            "service_type",
            "district",
            "rating",
            "review_text",
            "review_date",
            "verified_booking",
            "dataset_split",
        ],
        [
            {
                "review_id": "R1",
                "booking_id": "B1",
                "user_id": "U1",
                "provider_id": "SP1",
                "service_type": "Electrical",
                "district": "Colombo",
                "rating": "5",
                "review_text": "Good work",
                "review_date": "2025-01-01T00:00:00+00:00",
                "verified_booking": "1",
                "dataset_split": "train",
            },
            {
                "review_id": "R2",
                "booking_id": "B1",
                "user_id": "U2",
                "provider_id": "SP1",
                "service_type": "Electrical",
                "district": "Colombo",
                "rating": "1",
                "review_text": "Synthetic flagged review",
                "review_date": "2025-01-02T00:00:00+00:00",
                "verified_booking": "0",
                "dataset_split": "test",
            },
        ],
    )

    customers, provider_reviews, metadata = load_seed_data(
        reviews,
        provider_map,
        credibility,
    )

    assert set(customers) == {"RCU1", "RCU2"}
    assert customers["RCU1"]["profile"]["authentication"] == "none"
    assert customers["RCU1"]["profile"]["display_name"] == "Research Customer U1"
    assert len(provider_reviews["P00001"]) == 2
    assert provider_reviews["P00001"][0]["usable_for_ranking"] is True
    assert provider_reviews["P00001"][1]["is_fake_review"] is True
    assert provider_reviews["P00001"][1]["usable_for_ranking"] is False
    assert metadata["review_count"] == 2
    assert metadata["credible_review_count"] == 1
    assert metadata["provider_count"] == 1
    assert set(metadata["source_checksums"]) == {
        "raw_reviews",
        "provider_map",
        "credibility",
    }

    paths = {path for path, _ in iter_write_entries(customers, provider_reviews, metadata)}
    assert "research_customers/RCU1/reviews/R1" in paths
    assert "research_customers/RCU2/reviews/R2" in paths
    assert "research_provider_reviews/P00001/reviews/R1" in paths
    assert "research_provider_reviews/P00001/reviews/R2" in paths


def test_compatible_marker_locks_source_counts_and_checksums() -> None:
    metadata = {
        "seed_version": SEED_VERSION,
        "review_count": 2,
        "research_customer_count": 2,
        "provider_count": 1,
        "credible_review_count": 1,
        "source_checksums": {"reviews.csv": "abc"},
    }
    assert compatible_marker(dict(metadata), metadata)
    changed = dict(metadata, review_count=3)
    assert not compatible_marker(changed, metadata)
