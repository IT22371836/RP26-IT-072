from __future__ import annotations

import asyncio
from copy import deepcopy
from typing import Any

from app.core.config import Settings
from app.schemas.provider_identity import is_supported_provider_id


class FirebaseComponent2Error(RuntimeError):
    pass


class FirebaseRequestConflictError(FirebaseComponent2Error):
    pass


def _provider_skills(value: Any) -> list[str]:
    if isinstance(value, str):
        values = value.split(",")
    elif isinstance(value, list):
        values = value
    else:
        values = []
    return [str(item).strip() for item in values if str(item).strip()]


def _provider_number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def normalize_verified_provider_candidate(
    provider_id: str,
    profile: dict[str, Any],
) -> dict[str, Any] | None:
    """Normalize one verified Firebase/Mongo provider for live ML scoring."""

    canonical_id = str(provider_id).strip()
    if not is_supported_provider_id(canonical_id) or profile.get("verified") is not True:
        return None
    declared_ids = [profile.get("provider_id"), profile.get("id"), profile.get("uid")]
    if any(value is not None and str(value).strip() != canonical_id for value in declared_ids):
        return None
    provider_name = str(
        profile.get("provider_name")
        or profile.get("providerName")
        or profile.get("fullName")
        or profile.get("name")
        or ""
    ).strip()
    category = str(profile.get("category") or "").strip()
    district = str(profile.get("district") or "").strip()
    city = str(profile.get("city") or "").strip()
    if not all((provider_name, category, district, city)):
        return None
    rating = min(5.0, max(0.0, _provider_number(profile.get("rating"))))
    review_count = max(
        0,
        int(_provider_number(profile.get("review_count", profile.get("reviewCount")))),
    )
    booking_success_rate = min(
        1.0,
        max(
            0.0,
            _provider_number(
                profile.get("booking_success_rate", profile.get("bookingSuccessRate"))
            ),
        ),
    )
    interaction_count = max(
        0,
        int(
            _provider_number(
                profile.get("interaction_count", profile.get("interactionCount"))
            )
        ),
    )
    experience_years = max(
        0,
        int(
            _provider_number(
                profile.get("experience_years", profile.get("experienceYears"))
            )
        ),
    )
    skills = _provider_skills(profile.get("skills"))
    return {
        "provider_id": canonical_id,
        "provider_name": provider_name,
        "category": category,
        "district": district,
        "city": city,
        "skills": skills,
        "description": str(profile.get("description") or "").strip(),
        "experience_years": experience_years,
        "rating": rating,
        "review_count": review_count,
        "booking_success_rate": booking_success_rate,
        "interaction_count": interaction_count,
        "verified": True,
        "candidate_source": "firebase_verified",
    }


def merge_verified_provider_candidates(
    artifact_provider_ids: set[str],
    mongo_providers: list[dict[str, Any]],
    firebase_providers: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return verified, normalized, non-artifact providers with Firebase authoritative."""

    merged: dict[str, dict[str, Any]] = {}
    for source_name, providers in (
        ("mongo_verified", mongo_providers),
        ("firebase_verified", firebase_providers),
    ):
        for profile in providers:
            provider_id = str(
                profile.get("provider_id") or profile.get("id") or profile.get("uid") or ""
            ).strip()
            if not provider_id or provider_id in artifact_provider_ids:
                continue
            normalized = normalize_verified_provider_candidate(provider_id, profile)
            if normalized is not None:
                normalized["candidate_source"] = source_name
                merged[provider_id] = normalized
    return [merged[provider_id] for provider_id in sorted(merged)]


class FirebaseRtdbClient:
    """Trusted Firebase RTDB adapter used only by the backend pipeline worker."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _app(self):
        if not self.settings.firebase_project_id or not self.settings.firebase_database_url:
            raise FirebaseComponent2Error("Firebase RTDB is not configured")
        try:
            import firebase_admin
            from firebase_admin import credentials

            name = f"weda-rtdb-{self.settings.firebase_project_id}"
            try:
                return firebase_admin.get_app(name)
            except ValueError:
                credential = None
                path = self.settings.firebase_credentials_path
                if path:
                    if not path.is_file():
                        raise FirebaseComponent2Error(
                            f"Firebase Admin credential file does not exist: {path}"
                        ) from None
                    credential = credentials.Certificate(str(path))
                return firebase_admin.initialize_app(
                    credential,
                    {
                        "projectId": self.settings.firebase_project_id,
                        "databaseURL": self.settings.firebase_database_url,
                    },
                    name=name,
                )
        except FirebaseComponent2Error:
            raise
        except Exception as error:
            raise FirebaseComponent2Error("Firebase Admin initialization failed") from error

    def _reference(self, path: str):
        try:
            from firebase_admin import db

            return db.reference(path, app=self._app())
        except FirebaseComponent2Error:
            raise
        except Exception as error:
            raise FirebaseComponent2Error(f"Could not open Firebase path {path}") from error

    async def ping(self) -> bool:
        try:
            # The Admin SDK rejects the browser-only `.info/connected` path.
            # A shallow root read verifies credentials, project, URL, and access
            # without downloading the database contents.
            await asyncio.to_thread(self._reference("/").get, shallow=True)
        except Exception:
            return False
        return True

    async def get_customer(self, firebase_uid: str) -> dict[str, Any] | None:
        value = await asyncio.to_thread(self._reference(f"customers/{firebase_uid}").get)
        return value if isinstance(value, dict) else None

    async def get_customer_booking_history(
        self, firebase_uid: str
    ) -> dict[str, dict[str, Any]]:
        value = await asyncio.to_thread(
            self._reference(f"customers/{firebase_uid}/bookingHistory").get
        )
        if not isinstance(value, dict):
            return {}
        return {key: item for key, item in value.items() if isinstance(item, dict)}

    async def get_provider_reviews(
        self, provider_id: str
    ) -> dict[str, dict[str, Any]]:
        value = await asyncio.to_thread(
            self._reference(f"providers/{provider_id}/reviews").get
        )
        if not isinstance(value, dict):
            return {}
        return {key: item for key, item in value.items() if isinstance(item, dict)}

    async def create_provider_review(
        self,
        provider_id: str,
        booking_id: str,
        payload: dict[str, Any],
    ) -> bool:
        """Create one idempotent provider review for a verified booking."""

        provider = await asyncio.to_thread(
            self._reference(f"providers/{provider_id}").get
        )
        if not isinstance(provider, dict):
            raise FirebaseComponent2Error(
                f"Firebase provider {provider_id} does not exist"
            )
        reference = self._reference(f"providers/{provider_id}/reviews/{booking_id}")
        created = False

        def transaction(current: Any) -> Any:
            nonlocal created
            if current is None:
                created = True
                return deepcopy(payload)
            if (
                isinstance(current, dict)
                and current.get("booking_id") == booking_id
                and current.get("provider_id") == provider_id
                and current.get("customer_uid") == payload.get("customer_uid")
                and current.get("rating") == payload.get("rating")
                and current.get("review_text") == payload.get("review_text")
            ):
                return current
            raise FirebaseRequestConflictError(
                f"Firebase provider review {booking_id} already contains different data"
            )

        try:
            await asyncio.to_thread(reference.transaction, transaction)
            return created
        except FirebaseRequestConflictError:
            raise
        except Exception as error:
            if isinstance(error.__cause__, FirebaseRequestConflictError):
                raise error.__cause__ from error
            raise FirebaseComponent2Error("Firebase provider review creation failed") from error

    async def refresh_provider_review_statistics(
        self, provider_id: str
    ) -> dict[str, Any]:
        """Recalculate platform-only aggregates without replacing research ratings."""

        reviews = await self.get_provider_reviews(provider_id)
        ratings = [
            float(item["rating"])
            for item in reviews.values()
            if item.get("source") == "platform_booking"
            and isinstance(item.get("rating"), (int, float))
            and 1 <= float(item["rating"]) <= 5
        ]
        reviewed_at = sorted(
            str(item.get("reviewed_at"))
            for item in reviews.values()
            if item.get("source") == "platform_booking" and item.get("reviewed_at")
        )
        statistics = {
            "averageRating": sum(ratings) / len(ratings) if ratings else 0.0,
            "count": len(ratings),
            "lastReviewedAt": reviewed_at[-1] if reviewed_at else None,
            "source": "platform_booking_reviews",
        }
        try:
            await asyncio.to_thread(
                self._reference(f"providers/{provider_id}").update,
                {
                    "platformRating": statistics["averageRating"],
                    "platformReviewCount": statistics["count"],
                    "reviewStats": statistics,
                },
            )
        except Exception as error:
            raise FirebaseComponent2Error(
                "Firebase provider review statistics update failed"
            ) from error
        return statistics

    async def create_customer_booking(
        self,
        firebase_uid: str,
        booking_id: str,
        payload: dict[str, Any],
    ) -> bool:
        """Create an immutable booking identity and return whether it was newly created."""

        reference = self._reference(
            f"customers/{firebase_uid}/bookingHistory/{booking_id}"
        )
        created = False

        def transaction(current: Any) -> Any:
            nonlocal created
            if current is None:
                created = True
                return deepcopy(payload)
            if (
                isinstance(current, dict)
                and current.get("booking_id") == booking_id
                and current.get("request_id") == payload.get("request_id")
                and current.get("provider_id") == payload.get("provider_id")
            ):
                return current
            raise FirebaseRequestConflictError(
                f"Firebase booking {booking_id} already contains different data"
            )

        try:
            await asyncio.to_thread(reference.transaction, transaction)
            return created
        except FirebaseRequestConflictError:
            raise
        except Exception as error:
            if isinstance(error.__cause__, FirebaseRequestConflictError):
                raise error.__cause__ from error
            raise FirebaseComponent2Error("Firebase booking creation failed") from error

    async def update_customer_booking(
        self,
        firebase_uid: str,
        booking_id: str,
        updates: dict[str, Any],
    ) -> None:
        reference = self._reference(
            f"customers/{firebase_uid}/bookingHistory/{booking_id}"
        )

        def transaction(current: Any) -> Any:
            if not isinstance(current, dict):
                raise FirebaseRequestConflictError(
                    f"Firebase booking {booking_id} does not exist"
                )
            updated = deepcopy(current)
            updated.update(deepcopy(updates))
            return updated

        try:
            await asyncio.to_thread(reference.transaction, transaction)
        except FirebaseRequestConflictError:
            raise
        except Exception as error:
            if isinstance(error.__cause__, FirebaseRequestConflictError):
                raise error.__cause__ from error
            raise FirebaseComponent2Error("Firebase booking update failed") from error

    async def delete_customer_booking_if_matching(
        self,
        firebase_uid: str,
        booking_id: str,
        pipeline_run_id: str,
    ) -> None:
        reference = self._reference(
            f"customers/{firebase_uid}/bookingHistory/{booking_id}"
        )

        def delete_if_matching() -> None:
            current = reference.get()
            if (
                isinstance(current, dict)
                and current.get("pipeline_run_id") == pipeline_run_id
            ):
                # The Firebase Admin Python SDK rejects ``None`` from a
                # transaction callback, so deletion must use Reference.delete.
                # Booking IDs are immutable and unique, while the run-id check
                # prevents this compensating action from deleting another run.
                reference.delete()

        await asyncio.to_thread(delete_if_matching)

    async def get_identity_profile(
        self, firebase_uid: str
    ) -> tuple[str, dict[str, Any]] | None:
        """Resolve an authenticated UID to its authoritative RTDB application role."""

        matches: list[tuple[str, dict[str, Any]]] = []
        for role, collection in (
            ("customer", "customers"),
            ("provider", "providers"),
            ("admin", "admins"),
        ):
            value = await asyncio.to_thread(
                self._reference(f"{collection}/{firebase_uid}").get
            )
            if isinstance(value, dict):
                matches.append((role, value))
        if len(matches) > 1:
            raise FirebaseComponent2Error(
                f"Firebase UID {firebase_uid} has more than one application role"
            )
        return matches[0] if matches else None

    async def get_providers(self, provider_ids: list[str]) -> dict[str, dict[str, Any]]:
        async def read(provider_id: str) -> tuple[str, Any]:
            value = await asyncio.to_thread(self._reference(f"providers/{provider_id}").get)
            return provider_id, value

        values = await asyncio.gather(*(read(provider_id) for provider_id in provider_ids))
        return {key: value for key, value in values if isinstance(value, dict)}

    async def get_verified_provider_candidates(self) -> list[dict[str, Any]]:
        """Read and normalize only administrator-verified Firebase providers."""

        try:
            providers_reference = self._reference("providers")
            query = providers_reference.order_by_child("verified").equal_to(True)
            value = await asyncio.to_thread(query.get)
        except Exception as error:
            if "Index not defined" not in str(error):
                raise FirebaseComponent2Error(
                    "Firebase verified-provider lookup failed"
                ) from error
            try:
                # Keep local development operational before the additive
                # `providers/.indexOn` rule has been deployed. The same strict
                # normalization below still admits only verified profiles.
                value = await asyncio.to_thread(providers_reference.get)
            except Exception as fallback_error:
                raise FirebaseComponent2Error(
                    "Firebase verified-provider lookup failed"
                ) from fallback_error
        if not isinstance(value, dict):
            return []
        candidates = [
            normalize_verified_provider_candidate(str(provider_id), profile)
            for provider_id, profile in value.items()
            if isinstance(profile, dict)
        ]
        return [candidate for candidate in candidates if candidate is not None]

    async def create_filter_request(self, request_id: str, payload: dict[str, Any]) -> None:
        reference = self._reference(f"filter_requests/{request_id}")

        def transaction(current: Any) -> Any:
            if current is None:
                return deepcopy(payload)
            if current == payload:
                return current
            if (
                isinstance(current, dict)
                and current.get("pipeline", {}).get("run_id")
                == payload.get("pipeline", {}).get("run_id")
                and current.get("results", {}).get("provider_ids")
                == payload.get("results", {}).get("provider_ids")
            ):
                return current
            raise FirebaseRequestConflictError(
                f"Firebase filter request {request_id} already contains different data"
            )

        try:
            await asyncio.to_thread(reference.transaction, transaction)
        except FirebaseRequestConflictError:
            raise
        except Exception as error:
            if isinstance(error.__cause__, FirebaseRequestConflictError):
                raise error.__cause__ from error
            raise FirebaseComponent2Error("Firebase filter request creation failed") from error

    async def get_filter_request(self, request_id: str) -> dict[str, Any] | None:
        value = await asyncio.to_thread(
            self._reference(f"filter_requests/{request_id}").get
        )
        return value if isinstance(value, dict) else None

    async def complete_filter_request(
        self,
        request_id: str,
        *,
        output_results: dict[str, Any],
        pipeline_updates: dict[str, Any],
    ) -> None:
        updates: dict[str, Any] = {
            "output_results": output_results,
            "isNewRequest": False,
        }
        updates.update({f"pipeline/{key}": value for key, value in pipeline_updates.items()})
        try:
            await asyncio.to_thread(
                self._reference(f"filter_requests/{request_id}").update,
                updates,
            )
        except Exception as error:
            raise FirebaseComponent2Error("Firebase Component 2 output write failed") from error


def booking_history_preference_ids(
    history: dict[str, dict[str, Any]],
    *,
    limit: int = 500,
) -> list[str]:
    """Convert canonical Firebase booking states into Component 1 preference weights."""

    ordered = sorted(
        history.values(),
        key=lambda item: str(item.get("updated_at") or item.get("requested_at") or ""),
        reverse=True,
    )[:limit]
    preferences: list[str] = []
    for item in ordered:
        provider_id = item.get("provider_id")
        if not isinstance(provider_id, str) or not is_supported_provider_id(
            provider_id.strip()
        ):
            continue
        status = str(item.get("status") or "booking_requested")
        # Preserve the former interaction-event effect: selected (2) + requested
        # (3), then completed (4), then rated (4).
        weight = 5
        if status == "booking_completed":
            weight += 4
        if isinstance(item.get("rating"), int):
            weight += 4
        preferences.extend([provider_id] * min(weight, 13))
    return preferences
