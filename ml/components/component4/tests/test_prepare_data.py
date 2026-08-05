from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pandas as pd


MODULE_PATH = Path(__file__).resolve().parents[1] / "src" / "prepare_data.py"
SPEC = importlib.util.spec_from_file_location("component4_prepare_data", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
prepare_data = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = prepare_data
SPEC.loader.exec_module(prepare_data)


def test_review_normalization_and_grouping_are_stable() -> None:
    left = "  Excellent\tSERVICE!  "
    right = "excellent service!"
    assert prepare_data.normalize_review_text(left) == "excellent service!"
    assert prepare_data.review_text_group_id(left) == prepare_data.review_text_group_id(right)


def test_duplicate_texts_always_receive_the_same_split() -> None:
    group_id = prepare_data.review_text_group_id("Same review text")
    assert prepare_data.deterministic_split(group_id) == prepare_data.deterministic_split(group_id)
    assert prepare_data.deterministic_split(group_id) in {"train", "validation", "test"}


def test_category_aliases_match_active_component1_vocabulary() -> None:
    assert prepare_data.canonical_service_type("A/C Technicians") == "A/C"
    assert prepare_data.canonical_service_type("CCTV Technicians") == "CCTV"
    assert prepare_data.canonical_service_type("Ceiling Works") == "Ceiling"
    assert prepare_data.canonical_service_type("Tile Workers") == "Tile"
    assert prepare_data.canonical_service_type("Well Services") == "Wells"
    assert prepare_data.canonical_service_type("Plumbers") == "Plumbers"


def test_prepare_reviews_preserves_sources_and_removes_split_leakage() -> None:
    reviews = pd.DataFrame(
        {
            "review_id": ["R00001", "R00002", "R00003"],
            "booking_id": ["B1", "B1", "B3"],
            "provider_id": ["P1", "P2", "P3"],
            "user_id": ["U1", "U2", "U3"],
            "service_type": ["A/C Technicians", "A/C Technicians", "Plumbers"],
            "district": ["Colombo", "Galle", "Kandy"],
            "rating": [5, 4, 3],
            "review_text": ["Great work", " GREAT   WORK ", "Average work"],
            "review_date": ["2026-01-01", "2026-01-02", "2026-01-03"],
            "verified_booking": [1, 1, 0],
            "dataset_split": ["train", "test", "validation"],
        }
    )

    prepared = prepare_data.prepare_reviews(reviews)

    assert prepared["booking_id"].is_unique
    assert prepared["source_booking_id"].tolist() == ["B1", "B1", "B3"]
    assert prepared["source_dataset_split"].tolist() == ["train", "test", "validation"]
    assert prepared.loc[0, "service_type"] == "A/C"
    assert prepared.loc[0, "source_service_type"] == "A/C Technicians"
    assert prepared.loc[0, "review_text_group_id"] == prepared.loc[1, "review_text_group_id"]
    assert prepared.loc[0, "dataset_split"] == prepared.loc[1, "dataset_split"]
