import asyncio
from typing import Any

import pytest
from fastapi import Request
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import (
    get_customer_profile_repository,
    get_firebase_current_user,
    get_firebase_rtdb_client,
    get_interaction_repository,
    get_provider_repository,
    get_service_request_repository,
    get_user_repository,
)
from app.api.providers import document_storage_service
from app.core.config import get_settings
from app.core.security import decode_access_token_claims
from app.main import app
from app.repositories.providers import ProviderProfileExistsError
from app.repositories.users import DuplicateEmailError
from app.schemas.auth import UserPublic
from app.schemas.common import utc_now
from app.services.file_storage import DownloadedDocument, StoredDocument


class InMemoryUserRepository:
    def __init__(self) -> None:
        self.by_email: dict[str, dict[str, Any]] = {}
        self.by_id: dict[str, dict[str, Any]] = {}

    async def create(self, document: dict[str, Any]) -> dict[str, Any]:
        if document["email"] in self.by_email:
            raise DuplicateEmailError
        self.by_email[document["email"]] = document
        self.by_id[document["user_id"]] = document
        return document

    async def find_by_email(self, email: str) -> dict[str, Any] | None:
        return self.by_email.get(email)

    async def find_by_id(self, user_id: str) -> dict[str, Any] | None:
        return self.by_id.get(user_id)


class InMemoryProviderRepository:
    def __init__(self) -> None:
        self.by_id: dict[str, dict[str, Any]] = {}
        self.by_user_id: dict[str, dict[str, Any]] = {}
        self.verification_events: list[dict[str, Any]] = []

    async def create(self, document: dict[str, Any]) -> dict[str, Any]:
        if document["user_id"] in self.by_user_id:
            raise ProviderProfileExistsError
        self.by_id[document["provider_id"]] = document
        self.by_user_id[document["user_id"]] = document
        return document

    async def find_by_id(self, provider_id: str) -> dict[str, Any] | None:
        return self.by_id.get(provider_id)

    async def find_by_user_id(self, user_id: str) -> dict[str, Any] | None:
        return self.by_user_id.get(user_id)

    async def update_by_user_id(
        self, user_id: str, updates: dict[str, Any]
    ) -> dict[str, Any] | None:
        provider = self.by_user_id.get(user_id)
        if provider is not None:
            provider.update(updates)
        return provider

    async def add_document(
        self,
        user_id: str,
        category: str,
        document: dict[str, Any],
    ) -> dict[str, Any] | None:
        provider = self.by_user_id.get(user_id)
        if provider is None or provider.get("verified") or provider["documents"].get("status"):
            return None
        provider["documents"].setdefault(category, []).append(document)
        provider["updated_at"] = utc_now()
        return provider

    async def soft_delete_document(
        self,
        user_id: str,
        category: str,
        file_id: str,
    ) -> dict[str, Any] | None:
        provider = self.by_user_id.get(user_id)
        if provider is None or provider.get("verified") or provider["documents"].get("status"):
            return None
        item = next(
            (
                item
                for item in provider["documents"].get(category, [])
                if item["file_id"] == file_id and item.get("deleted_at") is None
            ),
            None,
        )
        if item is None:
            return None
        item["deleted_at"] = utc_now()
        provider["updated_at"] = utc_now()
        return provider

    async def request_document_verification(self, user_id: str) -> dict[str, Any] | None:
        provider = self.by_user_id.get(user_id)
        if provider is None or provider.get("verified") or provider["documents"].get("status"):
            return None
        provider["documents"]["status"] = True
        provider["documents"]["verified"] = False
        provider["updated_at"] = utc_now()
        return provider

    async def set_verification(
        self,
        provider_id: str,
        admin_user_id: str,
        verified: bool,
        reason: str | None,
    ) -> tuple[dict[str, Any], dict[str, Any]] | None:
        provider = self.by_id.get(provider_id)
        if provider is None:
            return None
        now = utc_now()
        event = {
            "event_id": f"V{len(self.verification_events) + 1}",
            "provider_id": provider_id,
            "admin_user_id": admin_user_id,
            "previous_verified": bool(provider.get("verified")),
            "verified": verified,
            "reason": reason,
            "created_at": now,
        }
        provider["verified"] = verified
        provider["documents"]["status"] = False
        provider["documents"]["verified"] = verified
        provider["verification"] = {
            **provider.get("verification", {}),
            "status": "verified" if verified else "revoked",
            "last_action_by": admin_user_id,
            "last_action_at": now,
            "last_reason": reason,
        }
        provider["updated_at"] = now
        self.verification_events.append(event)
        return provider, event

    async def list_verification_events(
        self, provider_id: str, limit: int = 100
    ) -> list[dict[str, Any]]:
        return [
            event
            for event in reversed(self.verification_events)
            if event["provider_id"] == provider_id
        ][:limit]

    async def list_all(self, limit: int = 10_000) -> list[dict[str, Any]]:
        return list(self.by_id.values())[:limit]

    async def update_statistics(
        self, provider_id: str, statistics: dict[str, int | float]
    ) -> dict[str, Any] | None:
        provider = self.by_id.get(provider_id)
        if provider is not None:
            provider.update(statistics)
        return provider


class InMemoryPrivateDocumentStorage:
    def __init__(self) -> None:
        self.download_calls: list[tuple[str, str | None]] = []

    def upload(self, **values: Any) -> StoredDocument:
        content = b"private-document"
        storage_path = (
            f"private/providers/{values['provider_id']}/{values['category']}/"
            f"{values['file_id']}_document.pdf"
        )
        url = f"gs://test-bucket/{storage_path}"
        return StoredDocument(
            file_url=url,
            current_url=url,
            storage_path=storage_path,
            content_sha256=(
                "d52953e6a7ff8b2f6f6d42c29de5133d6887d8ea675b516d56767f26d3379c77"
            ),
            content_type="application/pdf",
            format="PDF",
            size_bytes=len(content),
        )

    def download(self, file_url: str, expected_sha256: str | None) -> DownloadedDocument:
        self.download_calls.append((file_url, expected_sha256))
        return DownloadedDocument(
            content=b"private-document",
            content_type="application/pdf",
        )


class InMemoryServiceRequestRepository:
    def __init__(self) -> None:
        self.by_id: dict[str, dict[str, Any]] = {}

    async def create(self, document: dict[str, Any]) -> dict[str, Any]:
        self.by_id[document["request_id"]] = document
        return document

    async def find_by_id(self, request_id: str) -> dict[str, Any] | None:
        return self.by_id.get(request_id)

    async def list_for_user(self, user_id: str, limit: int = 50) -> list[dict[str, Any]]:
        records = [record for record in self.by_id.values() if record["user_id"] == user_id]
        return records[:limit]


class InMemoryCustomerProfileRepository:
    def __init__(self) -> None:
        self.by_user_id: dict[str, dict[str, Any]] = {}

    async def create(self, document: dict[str, Any]) -> dict[str, Any]:
        self.by_user_id[document["user_id"]] = document
        return document

    async def find_by_user_id(self, user_id: str) -> dict[str, Any] | None:
        return self.by_user_id.get(user_id)

    async def update_by_user_id(
        self, user_id: str, updates: dict[str, Any]
    ) -> dict[str, Any] | None:
        if user_id not in self.by_user_id:
            return None
        self.by_user_id[user_id].update(updates)
        return self.by_user_id[user_id]


class InMemoryInteractionRepository:
    def __init__(self) -> None:
        self.records: list[dict[str, Any]] = []

    async def create(self, document: dict[str, Any]) -> dict[str, Any]:
        self.records.append(document)
        return document

    async def create_many(self, documents: list[dict[str, Any]]) -> None:
        self.records.extend(documents)

    async def list_for_user(self, user_id: str, limit: int = 100) -> list[dict[str, Any]]:
        return [record for record in self.records if record["user_id"] == user_id][:limit]

    async def list_for_provider(self, provider_id: str, limit: int = 100) -> list[dict[str, Any]]:
        return [record for record in self.records if record["provider_id"] == provider_id][:limit]

    async def find_by_id(self, interaction_id: str) -> dict[str, Any] | None:
        return next(
            (record for record in self.records if record["interaction_id"] == interaction_id), None
        )

    async def has_event(
        self, user_id: str, request_id: str, provider_id: str, interaction_type: Any
    ) -> bool:
        return any(
            record["user_id"] == user_id
            and record["request_id"] == request_id
            and record["provider_id"] == provider_id
            and record["interaction_type"] == interaction_type.value
            for record in self.records
        )

    async def provider_statistics(self, provider_id: str) -> dict[str, int | float]:
        records = [record for record in self.records if record["provider_id"] == provider_id]
        completed = sum(record["interaction_type"] == "booking_completed" for record in records)
        cancelled = sum(record["interaction_type"] == "booking_cancelled" for record in records)
        ratings = [record["rating"] for record in records if record["interaction_type"] == "rated"]
        closed = completed + cancelled
        return {
            "rating": sum(ratings) / len(ratings) if ratings else 0.0,
            "review_count": len(ratings),
            "booking_success_rate": completed / closed if closed else 0.0,
            "interaction_count": sum(
                record["interaction_type"] != "impression" for record in records
            ),
        }

    async def preferred_provider_ids(self, user_id: str, limit: int = 500) -> list[str]:
        return [
            record["provider_id"]
            for record in self.records[:limit]
            if record["user_id"] == user_id and record["interaction_type"] != "impression"
        ]

    async def click_preference_provider_ids(
        self, user_id: str, limit: int = 500
    ) -> list[str]:
        return [
            record["provider_id"]
            for record in self.records[:limit]
            if record["user_id"] == user_id and record["interaction_type"] == "click"
        ]

    async def find_booking_requested(
        self, user_id: str, request_id: str, provider_id: str
    ) -> dict[str, Any] | None:
        return next(
            (
                record
                for record in self.records
                if record["user_id"] == user_id
                and record["request_id"] == request_id
                and record["provider_id"] == provider_id
                and record["interaction_type"] == "booking_requested"
            ),
            None,
        )


class InMemoryFirebaseBookingHistory:
    def __init__(self) -> None:
        self.by_uid: dict[str, dict[str, dict[str, Any]]] = {}
        self.provider_reviews: dict[str, dict[str, dict[str, Any]]] = {}
        self.provider_review_statistics: dict[str, dict[str, Any]] = {}

    async def get_customer_booking_history(
        self, firebase_uid: str
    ) -> dict[str, dict[str, Any]]:
        return self.by_uid.get(firebase_uid, {})

    async def create_customer_booking(
        self, firebase_uid: str, booking_id: str, payload: dict[str, Any]
    ) -> bool:
        history = self.by_uid.setdefault(firebase_uid, {})
        if booking_id in history:
            return False
        history[booking_id] = dict(payload)
        return True

    async def update_customer_booking(
        self, firebase_uid: str, booking_id: str, updates: dict[str, Any]
    ) -> None:
        self.by_uid[firebase_uid][booking_id].update(updates)

    async def create_provider_review(
        self, provider_id: str, booking_id: str, payload: dict[str, Any]
    ) -> bool:
        reviews = self.provider_reviews.setdefault(provider_id, {})
        if booking_id in reviews:
            return False
        reviews[booking_id] = dict(payload)
        return True

    async def refresh_provider_review_statistics(
        self, provider_id: str
    ) -> dict[str, Any]:
        ratings = [
            float(item["rating"])
            for item in self.provider_reviews.get(provider_id, {}).values()
        ]
        statistics = {
            "averageRating": sum(ratings) / len(ratings) if ratings else 0.0,
            "count": len(ratings),
        }
        self.provider_review_statistics[provider_id] = statistics
        return statistics


async def register_and_login(
    client: AsyncClient,
    role: str,
    email: str,
) -> tuple[dict[str, Any], dict[str, str]]:
    registration = await client.post(
        f"/api/v1/auth/register/{role}",
        json={
            "email": email,
            "password": "StrongPassword123!",
            "full_name": f"Test {role.title()}",
        },
    )
    assert registration.status_code == 201

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "StrongPassword123!"},
    )
    assert login.status_code == 200
    body = login.json()
    return registration.json(), {"Authorization": f"Bearer {body['access_token']}"}


@pytest.mark.skip(reason="Legacy FastAPI password-auth flow was removed in favor of Firebase Auth")
def test_customer_and_provider_authenticated_api_flow() -> None:
    async def run_test() -> None:
        users = InMemoryUserRepository()
        providers = InMemoryProviderRepository()
        requests = InMemoryServiceRequestRepository()
        customers = InMemoryCustomerProfileRepository()
        interactions = InMemoryInteractionRepository()
        firebase_bookings = InMemoryFirebaseBookingHistory()
        private_storage = InMemoryPrivateDocumentStorage()

        app.dependency_overrides[get_user_repository] = lambda: users
        app.dependency_overrides[get_provider_repository] = lambda: providers
        app.dependency_overrides[get_service_request_repository] = lambda: requests
        app.dependency_overrides[get_customer_profile_repository] = lambda: customers
        app.dependency_overrides[get_interaction_repository] = lambda: interactions
        app.dependency_overrides[get_firebase_rtdb_client] = lambda: firebase_bookings
        app.dependency_overrides[document_storage_service] = lambda: private_storage

        async def firebase_boundary_stub(request: Request) -> UserPublic:
            token = request.headers["Authorization"].removeprefix("Bearer ")
            claims = decode_access_token_claims(token, get_settings())
            users.by_id[claims.user_id].setdefault("legacy", {})["firebase_uid"] = (
                f"firebase-{claims.user_id}"
            )
            return UserPublic.model_validate(users.by_id[claims.user_id])

        app.dependency_overrides[get_firebase_current_user] = firebase_boundary_stub

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                customer, customer_headers = await register_and_login(
                    client, "customer", "customer-flow@example.com"
                )

                me = await client.get("/api/v1/auth/me", headers=customer_headers)
                assert me.status_code == 200
                assert me.json()["user_id"] == customer["user_id"]

                customer_profile = await client.get(
                    "/api/v1/customers/me", headers=customer_headers
                )
                assert customer_profile.status_code == 200
                assert customer_profile.json()["user_id"] == customer["user_id"]

                updated_profile = await client.patch(
                    "/api/v1/customers/me",
                    headers=customer_headers,
                    json={
                        "phone": "+94771234567",
                        "district": "Colombo",
                        "city": "Kottawa",
                        "preferred_language": "Sinhala",
                        "location": {"latitude": 6.8412, "longitude": 79.9654},
                    },
                )
                assert updated_profile.status_code == 200
                assert updated_profile.json()["city"] == "Kottawa"
                assert updated_profile.json()["location"] == {
                    "latitude": 6.8412,
                    "longitude": 79.9654,
                }

                image_update = await client.patch(
                    "/api/v1/customers/me",
                    headers=customer_headers,
                    json={"customerImage": "https://example.com/customer.png"},
                )
                assert image_update.status_code == 200
                assert image_update.json()["customer_image"] == (
                    "https://example.com/customer.png"
                )
                assert image_update.json()["preferred_language"] == "Sinhala"
                assert image_update.json()["location"] == {
                    "latitude": 6.8412,
                    "longitude": 79.9654,
                }

                service_request = await client.post(
                    "/api/v1/service-requests",
                    headers=customer_headers,
                    json={
                        "request_text": "Need CCTV technician for DVR configuration in Kottawa",
                        "category": "CCTV",
                        "district": "Colombo",
                        "city": "Kottawa",
                        "urgency": "urgent",
                    },
                )
                assert service_request.status_code == 201
                assert service_request.json()["request_id"].startswith("R")

                interaction = await client.post(
                    "/api/v1/interactions",
                    headers=customer_headers,
                    json={
                        "request_id": service_request.json()["request_id"],
                        "provider_id": "PTEST123",
                        "category": "CCTV",
                        "interaction_type": "click",
                    },
                )
                assert interaction.status_code == 201
                assert interaction.json()["interaction_id"].startswith("I")

                direct_rating = await client.post(
                    "/api/v1/interactions",
                    headers=customer_headers,
                    json={
                        "request_id": service_request.json()["request_id"],
                        "provider_id": "PTEST123",
                        "category": "CCTV",
                        "interaction_type": "rated",
                        "rating": 5,
                        "review_text": "This must not bypass booking verification.",
                    },
                )
                assert direct_rating.status_code == 422

                customer_provider_attempt = await client.post(
                    "/api/v1/providers/me",
                    headers=customer_headers,
                    json={
                        "provider_name": "Invalid Customer Provider",
                        "category": "CCTV",
                        "district": "Colombo",
                        "city": "Kottawa",
                        "experience_years": 1,
                        "skills": ["DVR configuration"],
                        "description": (
                            "This request must be rejected because the role is customer."
                        ),
                    },
                )
                assert customer_provider_attempt.status_code == 403

                _, provider_headers = await register_and_login(
                    client, "provider", "provider-flow@example.com"
                )
                provider_profile = await client.post(
                    "/api/v1/providers/me",
                    headers=provider_headers,
                    json={
                        "provider_name": "Metro CCTV Care",
                        "category": "CCTV",
                        "district": "Colombo",
                        "city": "Kottawa",
                        "experience_years": 6,
                        "skills": ["DVR configuration", "camera installation"],
                        "description": (
                            "Experienced CCTV provider serving homes and businesses in Kottawa."
                        ),
                    },
                )
                assert provider_profile.status_code == 201
                assert provider_profile.json()["provider_id"].startswith("P")

                working_hours = {
                    day: {"isOpen": day != "Sunday", "start": "08:00 AM", "end": "06:00 PM"}
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
                updated_provider = await client.patch(
                    "/api/v1/providers/me",
                    headers=provider_headers,
                    json={
                        "phone": "+94770001122",
                        "location": {"latitude": 6.8412, "longitude": 79.9654},
                        "providerImage": "https://example.com/provider.png",
                        "preferredLanguage": "Sinhala, English",
                        "nic": "199012345678",
                        "workingHours": working_hours,
                    },
                )
                assert updated_provider.status_code == 200
                private_provider = updated_provider.json()
                assert private_provider["phone"] == "+94770001122"
                assert private_provider["provider_image"] == "https://example.com/provider.png"
                assert private_provider["working_hours"]["monday"]["is_open"] is True
                assert private_provider["working_hours"]["sunday"]["is_open"] is False
                assert private_provider["nic"] == "199012345678"

                public_provider = await client.get(
                    f"/api/v1/providers/{provider_profile.json()['provider_id']}"
                )
                assert public_provider.status_code == 200
                assert "nic" not in public_provider.json()
                assert "working_hours" not in public_provider.json()
                assert "phone" not in public_provider.json()
                assert "documents" not in public_provider.json()

                empty_documents = await client.get(
                    "/api/v1/providers/me/documents",
                    headers=provider_headers,
                )
                assert empty_documents.status_code == 200
                assert empty_documents.json()["certification"] == []

                protected_upload = await client.post(
                    "/api/v1/providers/me/documents/certification/upload",
                    headers=provider_headers,
                    json={
                        "fileName": "Protected NVQ.pdf",
                        "dataUrl": "data:application/pdf;base64,JVBERi0xLjQ=",
                    },
                )
                assert protected_upload.status_code == 200
                protected_item = protected_upload.json()["documents"]["certification"][0]
                assert protected_item["file_url"].startswith("gs://test-bucket/private/")
                assert protected_item["current_url"] == protected_item["file_url"]
                assert protected_item["legacy_url"] is None
                assert len(protected_item["content_sha256"]) == 64

                protected_download = await client.get(
                    (
                        "/api/v1/providers/me/documents/certification/"
                        f"{protected_item['file_id']}/content"
                    ),
                    headers=provider_headers,
                )
                assert protected_download.status_code == 200
                assert protected_download.content == b"private-document"
                assert protected_download.headers["cache-control"] == "private, no-store"

                first_document = await client.post(
                    "/api/v1/providers/me/documents/certification",
                    headers=provider_headers,
                    json={
                        "fileId": "firebase-doc-001",
                        "fileName": "NVQ Level 4.pdf",
                        "fileUrl": "https://storage.example.com/nvq-level-4.pdf",
                        "format": "PDF",
                    },
                )
                assert first_document.status_code == 200
                first_item = next(
                    item
                    for item in first_document.json()["documents"]["certification"]
                    if item["file_id"] == "firebase-doc-001"
                )
                assert first_item["file_id"] == "firebase-doc-001"
                assert first_item["file_name"] == "NVQ Level 4.pdf"
                assert first_item["deleted_at"] is None

                deleted_document = await client.delete(
                    f"/api/v1/providers/me/documents/certification/{first_item['file_id']}",
                    headers=provider_headers,
                )
                assert deleted_document.status_code == 200
                deleted_item = next(
                    item
                    for item in deleted_document.json()["documents"]["certification"]
                    if item["file_id"] == "firebase-doc-001"
                )
                assert deleted_item["file_url"] == first_item["file_url"]
                assert deleted_item["deleted_at"] is not None

                active_document = await client.post(
                    "/api/v1/providers/me/documents/identity_document",
                    headers=provider_headers,
                    json={
                        "file_name": "Identity.png",
                        "file_url": "https://storage.example.com/identity.png",
                        "format": "PNG",
                    },
                )
                assert active_document.status_code == 200
                active_item = active_document.json()["documents"]["identity_document"][0]

                verification_request = await client.post(
                    "/api/v1/providers/me/request-document-verification",
                    headers=provider_headers,
                )
                assert verification_request.status_code == 200
                assert verification_request.json()["documents"]["status"] is True

                locked_delete = await client.delete(
                    f"/api/v1/providers/me/documents/identity_document/{active_item['file_id']}",
                    headers=provider_headers,
                )
                assert locked_delete.status_code == 409

                unauthorized_approval = await client.patch(
                    f"/api/v1/admin/providers/{provider_profile.json()['provider_id']}/verification",
                    headers=customer_headers,
                    json={"verified": True, "reason": "Customer must not approve"},
                )
                assert unauthorized_approval.status_code == 403

                admin, admin_headers = await register_and_login(
                    client, "customer", "admin-flow@example.com"
                )
                users.by_id[admin["user_id"]]["role"] = "admin"
                admin_login = await client.post(
                    "/api/v1/auth/login",
                    json={
                        "email": "admin-flow@example.com",
                        "password": "StrongPassword123!",
                    },
                )
                assert admin_login.status_code == 200
                admin_headers = {
                    "Authorization": f"Bearer {admin_login.json()['access_token']}"
                }

                admin_providers = await client.get(
                    "/api/v1/admin/providers",
                    headers=admin_headers,
                )
                assert admin_providers.status_code == 200
                admin_provider = next(
                    item
                    for item in admin_providers.json()
                    if item["provider_id"] == provider_profile.json()["provider_id"]
                )
                assert admin_provider["nic"] == "199012345678"
                assert admin_provider["documents"]["identity_document"][0]["file_url"] == (
                    "https://storage.example.com/identity.png"
                )

                admin_protected_download = await client.get(
                    (
                        f"/api/v1/admin/providers/{admin_provider['provider_id']}/documents/"
                        f"certification/{protected_item['file_id']}/content"
                    ),
                    headers=admin_headers,
                )
                assert admin_protected_download.status_code == 200
                assert admin_protected_download.content == b"private-document"

                approved = await client.patch(
                    f"/api/v1/admin/providers/{provider_profile.json()['provider_id']}/verification",
                    headers=admin_headers,
                    json={"verified": True, "reason": "Identity document reviewed"},
                )
                assert approved.status_code == 200
                assert approved.json()["verified"] is True
                assert approved.json()["documents"]["verified"] is True
                assert approved.json()["documents"]["status"] is False

                verification_events = await client.get(
                    f"/api/v1/admin/providers/{provider_profile.json()['provider_id']}/verification-events",
                    headers=admin_headers,
                )
                assert verification_events.status_code == 200
                assert verification_events.json()[0]["previous_verified"] is False
                assert verification_events.json()[0]["verified"] is True
                assert verification_events.json()[0]["reason"] == "Identity document reviewed"

                public_after_approval = await client.get(
                    f"/api/v1/providers/{provider_profile.json()['provider_id']}"
                )
                assert public_after_approval.json()["verified"] is True
                assert "documents" not in public_after_approval.json()

                revoked = await client.patch(
                    f"/api/v1/admin/providers/{provider_profile.json()['provider_id']}/verification",
                    headers=admin_headers,
                    json={"verified": False, "reason": "Annual renewal required"},
                )
                assert revoked.status_code == 200
                assert revoked.json()["verified"] is False

                verification_events = await client.get(
                    f"/api/v1/admin/providers/{provider_profile.json()['provider_id']}/verification-events",
                    headers=admin_headers,
                )
                assert len(verification_events.json()) == 2
                assert verification_events.json()[0]["previous_verified"] is True

                booking = await client.post(
                    "/api/v1/interactions",
                    headers=customer_headers,
                    json={
                        "request_id": service_request.json()["request_id"],
                        "provider_id": provider_profile.json()["provider_id"],
                        "provider_name": provider_profile.json()["provider_name"],
                        "category": "CCTV",
                        "interaction_type": "booking_requested",
                    },
                )
                assert booking.status_code == 201

                provider_jobs = await client.get(
                    "/api/v1/interactions/provider/me", headers=provider_headers
                )
                assert provider_jobs.status_code == 200
                assert provider_jobs.json()[0]["interaction_type"] == "booking_requested"

                completed = await client.post(
                    f"/api/v1/interactions/{booking.json()['interaction_id']}/complete",
                    headers=provider_headers,
                )
                assert completed.status_code == 200
                assert completed.json()["interaction_type"] == "booking_completed"

                rating = await client.post(
                    f"/api/v1/interactions/{completed.json()['interaction_id']}/rate",
                    headers=customer_headers,
                    json={
                        "rating": 5,
                        "review_text": "Excellent installation and helpful explanation.",
                    },
                )
                assert rating.status_code == 200
                assert rating.json()["rating"] == 5
                assert rating.json()["review_text"] == (
                    "Excellent installation and helpful explanation."
                )
                firebase_history = firebase_bookings.by_uid[
                    f"firebase-{customer['user_id']}"
                ]
                firebase_booking = firebase_history[booking.json()["interaction_id"]]
                assert firebase_booking["status"] == "booking_completed"
                assert firebase_booking["rating"] == 5
                assert firebase_booking["review_text"] == (
                    "Excellent installation and helpful explanation."
                )
                provider_id = provider_profile.json()["provider_id"]
                provider_review = firebase_bookings.provider_reviews[provider_id][
                    booking.json()["interaction_id"]
                ]
                assert provider_review["customer_uid"] == (
                    f"firebase-{customer['user_id']}"
                )
                assert provider_review["rating"] == 5
                assert provider_review["review_text"] == (
                    "Excellent installation and helpful explanation."
                )
                assert provider_review["verified_booking"] is True
                assert firebase_bookings.provider_review_statistics[provider_id] == {
                    "averageRating": 5.0,
                    "count": 1,
                }
                refreshed_provider = await client.get(
                    "/api/v1/providers/me", headers=provider_headers
                )
                assert refreshed_provider.json()["rating"] == 5
                assert refreshed_provider.json()["review_count"] == 1
                assert refreshed_provider.json()["booking_success_rate"] == 1

                duplicate_rating = await client.post(
                    f"/api/v1/interactions/{completed.json()['interaction_id']}/rate",
                    headers=customer_headers,
                    json={"rating": 4},
                )
                assert duplicate_rating.status_code == 409

                provider_request_attempt = await client.post(
                    "/api/v1/service-requests",
                    headers=provider_headers,
                    json={
                        "request_text": "Providers cannot create customer service requests",
                        "category": "CCTV",
                        "district": "Colombo",
                        "city": "Kottawa",
                        "urgency": "normal",
                    },
                )
                assert provider_request_attempt.status_code == 403
        finally:
            app.dependency_overrides.clear()

    asyncio.run(run_test())
