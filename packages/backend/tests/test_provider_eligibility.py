from app.services.provider_eligibility import (
    eligible_provider_pool,
    runtime_pipeline_eligible,
    select_research_baseline,
)


def hours() -> dict:
    return {
        day: {"isOpen": True, "start": "08:00 AM", "end": "06:00 PM"}
        for day in (
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday",
        )
    }


def profile(provider_id: str, source: str, *, eligible: bool = True) -> dict:
    return {
        "id": provider_id,
        "uid": provider_id,
        "provider_id": provider_id,
        "fullName": "Ready Provider",
        "category": "Electricians",
        "district": "Colombo",
        "city": "Colombo",
        "nic": "200012345678",
        "phone": "+94770000000",
        "preferredLanguage": "Sinhala, English",
        "providerImage": "https://example.test/provider.png",
        "location": {"latitude": 6.9, "longitude": 79.9},
        "workingHours": hours(),
        "verified": True,
        "profileSource": source,
        "pipelineEligibility": {
            "version": 1,
            "eligible": eligible,
            "verified": True,
            "c1Ready": True,
            "c2Ready": True,
            "c4Ready": True,
            "profileComplete": True,
            "relationsValid": True,
            "activeResearchBaseline": source == "research_seed",
            "selectionVersion": "research-balanced-category-location-v1",
        },
    }


def test_runtime_gate_rejects_unverified_or_incomplete_profiles() -> None:
    ready = profile("P001", "research_seed")
    assert runtime_pipeline_eligible(ready) is True

    unverified = {**ready, "verified": False}
    assert runtime_pipeline_eligible(unverified) is False

    incomplete = {**ready, "workingHours": {}}
    assert runtime_pipeline_eligible(incomplete) is False

    missing_standard_field = {**ready, "nic": ""}
    assert runtime_pipeline_eligible(missing_standard_field) is False


def test_pool_is_verified_research_intersection_plus_verified_website() -> None:
    research = profile("P001", "research_seed")
    website = profile("firebase-auth-uid-12345", "web_registration")
    unmapped_research = profile("P999", "research_seed")
    legacy = profile("legacy-provider-12345", "legacy_unknown")

    pool = eligible_provider_pool(
        [research, website, unmapped_research, legacy],
        {"P001", "P002"},
    )

    assert pool.allowed_provider_ids == {"P001", "firebase-auth-uid-12345"}
    assert pool.research_count == 1
    assert pool.website_count == 1


def test_research_baseline_is_exact_deterministic_and_balanced() -> None:
    profiles = [
        {
            "provider_id": f"P{category:02d}{index:03d}",
            "category": f"Category {category:02d}",
            "district": f"District {index % 10:02d}",
            "city": f"City {index % 20:02d}",
        }
        for category in range(14)
        for index in range(100)
    ]
    shared_ids = {str(item["provider_id"]) for item in profiles}

    first = select_research_baseline(profiles, shared_ids, 1_000)
    second = select_research_baseline(reversed(profiles), shared_ids, 1_000)

    assert len(first.provider_ids) == 1_000
    assert first.provider_ids == second.provider_ids
    assert sorted(first.category_counts.values()) == [71] * 8 + [72] * 6
    for category in first.category_counts:
        selected = [
            item
            for item in profiles
            if item["provider_id"] in first.provider_ids
            and item["category"] == category
        ]
        assert len({item["district"] for item in selected}) == 10
