from scripts.prune_inactive_research_providers import (
    choose_booking_preserving_swaps,
    is_inactive_research,
    meaningful_provider_ids,
    promoted_profile,
)


def profile(*, active: bool, category: str = "Tile", district: str = "Colombo"):
    return {
        "researchSeed": True,
        "profileSource": "research_seed",
        "category": category,
        "district": district,
        "pipelineEligibility": {
            "activeResearchBaseline": active,
            "eligible": active,
        },
    }


def test_inactive_research_requires_both_false_flags() -> None:
    assert is_inactive_research("P00001", profile(active=False)) is True
    assert is_inactive_research("P00001", profile(active=True)) is False
    assert is_inactive_research("WEB1", profile(active=False)) is False


def test_meaningful_references_exclude_impressions_and_include_bookings() -> None:
    interactions = {
        "I1": {"provider_id": "P1", "interaction_type": "impression"},
        "I2": {"provider_id": "P2", "interaction_type": "selected"},
    }
    customers = {
        "C1": {"bookingHistory": {"B1": {"provider_id": "P3"}}}
    }

    assert meaningful_provider_ids(interactions, customers) == {"P2", "P3"}


def test_swap_preserves_category_and_avoids_referenced_active_provider() -> None:
    providers = {
        "P1": profile(active=False, category="Tile", district="Matara"),
        "P2": profile(active=True, category="Tile", district="Colombo"),
        "P3": profile(active=True, category="Tile", district="Colombo"),
        "P4": profile(active=True, category="Tile", district="Kandy"),
    }

    swaps = choose_booking_preserving_swaps(providers, {"P1"}, {"P1", "P2"})

    assert swaps == {"P1": "P3"}


def test_promoted_profile_keeps_data_and_enables_pipeline() -> None:
    original = {**profile(active=False), "fullName": "Booked Provider"}

    promoted = promoted_profile(original)

    assert promoted["fullName"] == "Booked Provider"
    assert promoted["pipelineEligibility"]["eligible"] is True
    assert promoted["pipelineEligibility"]["activeResearchBaseline"] is True
    assert promoted["pipelineEligibility"]["selectionReason"] == (
        "promoted_to_preserve_existing_booking"
    )
