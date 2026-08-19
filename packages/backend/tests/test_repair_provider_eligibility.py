from types import SimpleNamespace

from scripts.repair_provider_eligibility import build_updates, canonical_sha256


def working_hours() -> dict:
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


def base_profile(provider_id: str, email: str) -> dict:
    return {
        "id": provider_id,
        "uid": provider_id,
        "fullName": "Ready Provider",
        "email": email,
        "role": "provider",
        "category": "Masons",
        "district": "Colombo",
        "city": "Colombo",
        "location": {"latitude": 6.9, "longitude": 79.9},
        "workingHours": working_hours(),
    }


def test_repair_backfills_research_and_verifies_only_complete_sources() -> None:
    research = {**base_profile("P00001", "p1@example.test"), "researchSeed": True}
    website = {
        **base_profile("web-firebase-uid", "web@example.test"),
        "nic": "200012345678",
        "phone": "+94770000000",
        "preferredLanguage": "Sinhala, English",
        "providerImage": "https://example.test/provider.png",
    }
    legacy = {"id": "legacy", "uid": "legacy", "fullName": "Incomplete"}
    auth_users = {
        provider_id: SimpleNamespace(email=email, display_name=name)
        for provider_id, email, name in (
            ("P00001", "p1@example.test", "Research"),
            ("web-firebase-uid", "web@example.test", "Web"),
        )
    }

    updates, plan = build_updates(
        {"P00001": research, "web-firebase-uid": website, "legacy": legacy},
        {},
        {},
        auth_users,
        {"P00001"},
        {"P00001"},
        {"P00001"},
        provider_filter=None,
        source_filter=None,
        limit=None,
    )

    repaired_research = updates["providers/P00001"]
    assert repaired_research["verified"] is True
    assert repaired_research["nic"] == "RESEARCH-P00001"
    assert repaired_research["pipelineEligibility"]["profileComplete"] is True
    assert repaired_research["pipelineEligibility"]["activeResearchBaseline"] is True
    assert updates["providers/web-firebase-uid"]["verified"] is True
    assert updates["providers/legacy"]["verified"] is False
    assert plan["counts"]["eligible"] == 2
    assert [item["provider_id"] for item in plan["quarantined"]] == ["legacy"]


def test_component2_hash_is_order_independent() -> None:
    assert canonical_sha256({"b": 2, "a": 1}) == canonical_sha256({"a": 1, "b": 2})
