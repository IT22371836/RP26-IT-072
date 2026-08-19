import asyncio

from app.repositories.providers import ProviderRepository


class EligibleStore:
    def __init__(self) -> None:
        self.calls = 0

    async def query_equal(self, path: str, child: str, value: bool) -> dict:
        self.calls += 1
        assert path == "providers"
        assert child == "pipelineEligibility/eligible"
        assert value is True
        return {
            "web-uid": {"id": "web-uid", "fullName": "Website Provider"},
            "P00001": {"id": "P00001", "fullName": "Research Provider"},
        }


class VerificationStore:
    def __init__(self) -> None:
        self.updated: dict = {}
        self.provider = {
            "id": "web-uid",
            "uid": "web-uid",
            "userId": "UWEB1",
            "fullName": "Website Provider",
            "role": "provider",
            "profileSource": "web_registration",
            "category": "Masons",
            "district": "Colombo",
            "city": "Colombo",
            "nic": "200012345678",
            "phone": "+94770000000",
            "preferredLanguage": "Sinhala, English",
            "providerImage": "https://example.test/provider.png",
            "location": {"latitude": 6.9, "longitude": 79.9},
            "workingHours": {
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
            },
            "verified": False,
        }

    async def get(self, path: str) -> dict | None:
        if path == "providers/web-uid":
            return self.provider
        if path == "core/users/UWEB1":
            return {
                "role": "provider",
                "legacy": {"firebase_uid": "web-uid"},
            }
        return None

    async def multi_update(self, updates: dict) -> None:
        self.updated = updates


def test_pipeline_eligible_query_uses_index_and_process_cache() -> None:
    repository = ProviderRepository(object())
    store = EligibleStore()
    repository.store = store  # type: ignore[assignment]

    first = asyncio.run(repository.list_pipeline_eligible(cache_seconds=60))
    second = asyncio.run(repository.list_pipeline_eligible(cache_seconds=60))

    assert [item["provider_id"] for item in first] == ["P00001", "web-uid"]
    assert second == first
    assert store.calls == 1


def test_expired_cache_returns_immediately_and_refreshes_in_background() -> None:
    async def run() -> tuple[list[dict], int]:
        repository = ProviderRepository(object())
        store = EligibleStore()
        repository.store = store  # type: ignore[assignment]
        await repository.list_pipeline_eligible(cache_seconds=0)
        stale = await repository.list_pipeline_eligible(cache_seconds=60)
        assert repository._eligible_refresh_task is not None
        await repository._eligible_refresh_task
        return stale, store.calls

    stale, calls = asyncio.run(run())

    assert [item["provider_id"] for item in stale] == ["P00001", "web-uid"]
    assert calls == 2


def test_admin_verification_makes_complete_website_provider_pipeline_eligible() -> None:
    repository = ProviderRepository(object())
    store = VerificationStore()
    repository.store = store  # type: ignore[assignment]

    result = asyncio.run(
        repository.set_verification("web-uid", "UADMIN", True, "Documents checked")
    )

    assert result is not None
    provider, _ = result
    assert provider["verified"] is True
    assert provider["pipelineEligibility"]["eligible"] is True
    assert provider["pipelineEligibility"]["selectionReason"] == (
        "verified_website_registration"
    )
    assert "providers/web-uid" in store.updated
