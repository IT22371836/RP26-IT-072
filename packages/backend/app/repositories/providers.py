from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.repositories.concurrency import ProfileConcurrencyError
from app.repositories.firebase_store import FirebaseStore, nested_set, sorted_records
from app.schemas.common import new_public_id, utc_now


class ProviderProfileExistsError(Exception):
    pass


def _normalize(provider_id: str, value: dict[str, Any]) -> dict[str, Any]:
    document = deepcopy(value)
    aliases = {
        "provider_id": ("provider_id", "id", "uid"),
        "provider_name": ("provider_name", "providerName", "fullName", "name"),
        "experience_years": ("experience_years", "experienceYears"),
        "review_count": ("review_count", "reviewCount", "platformReviewCount"),
        "booking_success_rate": ("booking_success_rate", "bookingSuccessRate"),
        "interaction_count": ("interaction_count", "interactionCount"),
        "preferred_language": ("preferred_language", "preferredLanguage"),
        "provider_image": ("provider_image", "providerImage"),
        "working_hours": ("working_hours", "workingHours"),
    }
    for target, sources in aliases.items():
        if document.get(target) is None:
            document[target] = next(
                (document.get(source) for source in sources if document.get(source) is not None),
                None,
            )
    document["provider_id"] = document.get("provider_id") or provider_id
    document.setdefault("user_id", provider_id)
    document.setdefault("rating", float(document.get("platformRating") or 0.0))
    document.setdefault("review_count", 0)
    document.setdefault("booking_success_rate", 0.0)
    document.setdefault("interaction_count", 0)
    document.setdefault("experience_years", 0)
    document.setdefault("skills", [])
    document.setdefault("description", "")
    document.setdefault("documents", {"status": False, "verified": False})
    return document


class ProviderRepository:
    PATH = "providers"

    def __init__(self, database: Any) -> None:
        self.store = FirebaseStore(database)

    async def ensure_indexes(self) -> None:
        return None

    async def create(self, document: dict[str, Any]) -> dict[str, Any]:
        provider_id = str(document["provider_id"])
        if (
            await self.find_by_id(provider_id) is not None
            or await self.find_by_user_id(str(document["user_id"])) is not None
        ):
            raise ProviderProfileExistsError
        await self.store.multi_update(
            {
                f"{self.PATH}/{provider_id}": document,
                f"core/indexes/providers_by_user/{document['user_id']}": provider_id,
            }
        )
        return document

    async def find_by_id(self, provider_id: str) -> dict[str, Any] | None:
        value = await self.store.get(f"{self.PATH}/{provider_id}")
        return _normalize(provider_id, value) if isinstance(value, dict) else None

    async def find_by_user_id(self, user_id: str) -> dict[str, Any] | None:
        provider_id = await self.store.get(f"core/indexes/providers_by_user/{user_id}")
        if isinstance(provider_id, str):
            return await self.find_by_id(provider_id)
        user = await self.store.get(f"core/users/{user_id}")
        firebase_uid = (
            user.get("legacy", {}).get("firebase_uid") if isinstance(user, dict) else None
        )
        if isinstance(firebase_uid, str):
            direct = await self.find_by_id(firebase_uid)
            if direct is not None:
                await self.store.set(f"core/indexes/providers_by_user/{user_id}", firebase_uid)
                return {**direct, "user_id": user_id}
        values = await self.store.get(self.PATH) or {}
        for key, item in values.items():
            if isinstance(item, dict) and item.get("user_id") == user_id:
                await self.store.set(f"core/indexes/providers_by_user/{user_id}", key)
                return _normalize(key, item)
        return None

    async def update_by_user_id(
        self,
        user_id: str,
        updates: dict[str, Any],
        *,
        expected_updated_at: Any | None = None,
    ) -> dict[str, Any] | None:
        existing = await self.find_by_user_id(user_id)
        if existing is None:
            return None
        provider_id = str(existing["provider_id"])
        conflict = False

        def apply(current: Any) -> Any:
            nonlocal conflict
            if not isinstance(current, dict):
                return current
            if expected_updated_at is not None and str(current.get("updated_at")) != str(
                expected_updated_at
            ):
                conflict = True
                return current
            for key, item in updates.items():
                nested_set(current, key, item)
            return current

        updated = await self.store.transaction(f"{self.PATH}/{provider_id}", apply)
        if conflict:
            raise ProfileConcurrencyError
        return _normalize(provider_id, updated) if isinstance(updated, dict) else None

    async def add_document(
        self, user_id: str, category: str, document: dict[str, Any]
    ) -> dict[str, Any] | None:
        provider = await self.find_by_user_id(user_id)
        if (
            provider is None
            or provider.get("verified") is True
            or provider.get("documents", {}).get("status") is True
        ):
            return None
        documents = provider.setdefault("documents", {}).setdefault(category, [])
        if any(
            item.get("file_id") == document["file_id"]
            for item in documents
            if isinstance(item, dict)
        ):
            return None
        documents.append(document)
        provider["updated_at"] = utc_now()
        await self.store.set(f"{self.PATH}/{provider['provider_id']}", provider)
        return provider

    async def soft_delete_document(
        self, user_id: str, category: str, file_id: str
    ) -> dict[str, Any] | None:
        provider = await self.find_by_user_id(user_id)
        if (
            provider is None
            or provider.get("verified") is True
            or provider.get("documents", {}).get("status") is True
        ):
            return None
        found = False
        for item in provider.get("documents", {}).get(category, []):
            if (
                isinstance(item, dict)
                and item.get("file_id") == file_id
                and item.get("deleted_at") is None
            ):
                item["deleted_at"] = utc_now()
                found = True
                break
        if not found:
            return None
        provider["updated_at"] = utc_now()
        await self.store.set(f"{self.PATH}/{provider['provider_id']}", provider)
        return provider

    async def request_document_verification(self, user_id: str) -> dict[str, Any] | None:
        provider = await self.find_by_user_id(user_id)
        if (
            provider is None
            or provider.get("verified") is True
            or provider.get("documents", {}).get("status") is True
        ):
            return None
        provider.setdefault("documents", {}).update({"status": True, "verified": False})
        provider["updated_at"] = utc_now()
        await self.store.set(f"{self.PATH}/{provider['provider_id']}", provider)
        return provider

    async def set_verification(
        self, provider_id: str, admin_user_id: str, verified: bool, reason: str | None
    ) -> tuple[dict[str, Any], dict[str, Any]] | None:
        provider = await self.find_by_id(provider_id)
        if provider is None:
            return None
        now = utc_now()
        event = {
            "event_id": new_public_id("V"),
            "provider_id": provider_id,
            "admin_user_id": admin_user_id,
            "previous_verified": bool(provider.get("verified", False)),
            "verified": verified,
            "reason": reason,
            "created_at": now,
        }
        provider["verified"] = verified
        provider.setdefault("documents", {}).update({"status": False, "verified": verified})
        provider["verification"] = {
            **provider.get("verification", {}),
            "status": "verified" if verified else "revoked",
            "last_action_by": admin_user_id,
            "last_action_at": now,
            "last_reason": reason,
        }
        provider["updated_at"] = now
        await self.store.multi_update(
            {
                f"{self.PATH}/{provider_id}": provider,
                f"core/provider_verification_events/{event['event_id']}": event,
            }
        )
        return provider, event

    async def list_verification_events(
        self, provider_id: str, limit: int = 100
    ) -> list[dict[str, Any]]:
        values = await self.store.get("core/provider_verification_events") or {}
        selected = {
            key: item
            for key, item in values.items()
            if isinstance(item, dict) and item.get("provider_id") == provider_id
        }
        return sorted_records(selected, field="created_at", limit=limit)

    async def list_all(self, limit: int = 10_000) -> list[dict[str, Any]]:
        values = await self.store.get(self.PATH) or {}
        return [
            _normalize(key, item)
            for key, item in list(values.items())[:limit]
            if isinstance(item, dict)
        ]

    async def list_by_ids(self, provider_ids: list[str]) -> list[dict[str, Any]]:
        if not provider_ids:
            return []
        results = []
        for provider_id in provider_ids:
            item = await self.find_by_id(provider_id)
            if item is not None:
                results.append(item)
        return results

    async def count(self) -> int:
        return len(await self.store.shallow(self.PATH))

    async def update_statistics(
        self, provider_id: str, statistics: dict[str, int | float]
    ) -> dict[str, Any] | None:
        provider = await self.find_by_id(provider_id)
        if provider is None:
            return None
        provider.update(statistics)
        provider["updated_at"] = utc_now()
        await self.store.set(f"{self.PATH}/{provider_id}", provider)
        return provider
