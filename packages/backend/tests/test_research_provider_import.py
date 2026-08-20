from scripts.import_pipeline_providers import (
    canonical_user_id,
    load_population,
    research_email,
    rtdb_provider,
)


def test_exact_shared_provider_population_and_canonical_identities() -> None:
    providers = load_population(None, None)
    assert len(providers) == 4_998
    counts: dict[str, int] = {}
    for provider in providers:
        counts[provider["category"]] = counts.get(provider["category"], 0) + 1
        provider_id = provider["provider_id"]
        assert canonical_user_id(provider_id) == f"U{provider_id[1:]}"
        assert research_email(provider_id, provider["provider_name"]) == (
            f"{''.join(character for character in provider['provider_name'].lower() if character.isalnum())}"
            f"12.{provider_id.lower()}@gmail.com"
        )
    assert len(counts) == 14
    assert set(counts.values()) == {357}


def test_import_scope_controls_are_deterministic() -> None:
    first = load_population("Masons", 3)
    second = load_population("Masons", 3)
    assert [item["provider_id"] for item in first] == [
        item["provider_id"] for item in second
    ]
    assert all(item["category"] == "Masons" for item in first)


def test_research_provider_has_complete_verified_pipeline_profile() -> None:
    provider = rtdb_provider(load_population("Masons", 1)[0], "TEST-IMPORT")

    assert provider["verified"] is True
    assert provider["profileSource"] == "research_seed"
    assert provider["pipelineEligibility"]["eligible"] is True
    assert provider["pipelineEligibility"]["profileComplete"] is True
    assert provider["nic"].startswith("RESEARCH-")
    assert provider["phone"].startswith("research-")
    assert provider["preferredLanguage"] == "Sinhala, English"
    assert provider["providerImage"].startswith("https://")
