import asyncio
import json
from pathlib import Path

from app.core.config import Settings
from app.integrations.firebase_component2 import (
    FirebaseRtdbClient,
    merge_verified_provider_candidates,
    normalize_verified_provider_candidate,
)
from app.pipeline.schemas import PipelineSelectionRequest


FIREBASE_UID = "GsMrbJuYYHR7d0uKEqA5OVjdKV73"
SECOND_FIREBASE_UID = "PTygPQf3yzZlnRaG6Q9PZCKwm0s2"


def profile(**overrides) -> dict:
    return {
        "id": FIREBASE_UID,
        "uid": FIREBASE_UID,
        "fullName": "Verified Web Electrician",
        "category": "Electricians",
        "district": "Colombo",
        "city": "Moratuwa",
        "skills": ["House wiring", "Socket repair"],
        "description": "Verified electrician registered through WEB",
        "experienceYears": 6,
        "verified": True,
        **overrides,
    }


def test_verified_firebase_profile_is_normalized_for_ml_components() -> None:
    candidate = normalize_verified_provider_candidate(FIREBASE_UID, profile())

    assert candidate is not None
    assert candidate["provider_id"] == FIREBASE_UID
    assert candidate["provider_name"] == "Verified Web Electrician"
    assert candidate["experience_years"] == 6
    assert candidate["rating"] == 0
    assert candidate["skills"] == ["House wiring", "Socket repair"]


def test_unverified_or_identity_mismatched_firebase_profile_is_excluded() -> None:
    assert normalize_verified_provider_candidate(
        FIREBASE_UID, profile(verified=False)
    ) is None
    assert normalize_verified_provider_candidate(
        FIREBASE_UID, profile(id=SECOND_FIREBASE_UID, uid=SECOND_FIREBASE_UID)
    ) is None


def test_merge_deduplicates_artifacts_and_prefers_firebase_live_profile() -> None:
    mongo = [
        {
            **profile(),
            "provider_id": FIREBASE_UID,
            "id": FIREBASE_UID,
            "uid": FIREBASE_UID,
            "fullName": "Stale Mongo Name",
        },
        {**profile(), "provider_id": "P00001", "id": "P00001", "uid": "P00001"},
    ]
    firebase = [profile(fullName="Current Firebase Name")]

    candidates = merge_verified_provider_candidates({"P00001"}, mongo, firebase)

    assert len(candidates) == 1
    assert candidates[0]["provider_id"] == FIREBASE_UID
    assert candidates[0]["provider_name"] == "Current Firebase Name"
    assert candidates[0]["candidate_source"] == "firebase_verified"


def test_firebase_client_queries_only_verified_provider_index() -> None:
    calls: list[tuple[str, object]] = []

    class Query:
        def order_by_child(self, field: str):
            calls.append(("order_by_child", field))
            return self

        def equal_to(self, value: object):
            calls.append(("equal_to", value))
            return self

        def get(self):
            calls.append(("get", True))
            return {FIREBASE_UID: profile()}

    client = FirebaseRtdbClient(Settings(_env_file=None))
    client._reference = lambda path: (calls.append(("path", path)) or Query())  # type: ignore[method-assign]

    candidates = asyncio.run(client.get_verified_provider_candidates())

    assert [candidate["provider_id"] for candidate in candidates] == [FIREBASE_UID]
    assert calls == [
        ("path", "providers"),
        ("order_by_child", "verified"),
        ("equal_to", True),
        ("get", True),
    ]


def test_firebase_client_falls_back_until_verified_index_is_deployed() -> None:
    calls: list[str] = []

    class Query:
        def order_by_child(self, _field: str):
            return self

        def equal_to(self, _value: object):
            return self

        def get(self):
            calls.append("query")
            raise RuntimeError('Index not defined, add ".indexOn": "verified"')

    class Reference(Query):
        def order_by_child(self, _field: str):
            return Query()

        def get(self):
            calls.append("fallback")
            return {
                FIREBASE_UID: profile(),
                SECOND_FIREBASE_UID: profile(
                    id=SECOND_FIREBASE_UID,
                    uid=SECOND_FIREBASE_UID,
                    verified=False,
                ),
            }

    client = FirebaseRtdbClient(Settings(_env_file=None))
    client._reference = lambda _path: Reference()  # type: ignore[method-assign]

    candidates = asyncio.run(client.get_verified_provider_candidates())

    assert [candidate["provider_id"] for candidate in candidates] == [FIREBASE_UID]
    assert calls == ["query", "fallback"]


def test_selection_and_rules_support_verified_firebase_provider_ids() -> None:
    assert PipelineSelectionRequest(provider_id=FIREBASE_UID).provider_id == FIREBASE_UID
    repository_root = Path(__file__).resolve().parents[3]
    rules = json.loads((repository_root / "database.rules.json").read_text("utf-8"))
    assert rules["rules"]["providers"][".indexOn"] == ["verified"]
