from scripts.migrate_research_provider_credentials import (
    desired_emails,
    email_key,
    provider_name_slug,
    research_email,
)


def active_profile(name: str) -> dict:
    return {
        "fullName": name,
        "researchSeed": True,
        "profileSource": "research_seed",
        "pipelineEligibility": {
            "activeResearchBaseline": True,
            "eligible": True,
        },
    }


def test_provider_name_slug_is_email_safe() -> None:
    assert provider_name_slug("City A/C & Electrical") == "cityacelectrical"
    assert provider_name_slug("  ") == "provider"


def test_research_email_uses_name_pattern_and_provider_id_for_uniqueness() -> None:
    assert research_email("P03059", "Nimal Perera") == (
        "nimalperera12.p03059@gmail.com"
    )
    assert research_email("P03060", "Nimal Perera") == (
        "nimalperera12.p03060@gmail.com"
    )


def test_desired_emails_are_unique_for_duplicate_names(monkeypatch) -> None:
    monkeypatch.setattr(
        "scripts.migrate_research_provider_credentials.EXPECTED_RESEARCH_ACCOUNTS", 2
    )
    mapping = desired_emails(
        {
            "P00001": active_profile("Nimal Perera"),
            "P00002": active_profile("Nimal Perera"),
        }
    )

    assert len(set(mapping.values())) == 2


def test_email_index_key_is_normalized() -> None:
    assert email_key(" Name12.P00001@GMAIL.COM ") == email_key(
        "name12.p00001@gmail.com"
    )
