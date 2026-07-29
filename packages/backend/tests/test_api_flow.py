import asyncio
from typing import Any

from httpx import ASGITransport, AsyncClient

from app.api.dependencies import (
    get_customer_profile_repository,
    get_interaction_repository,
    get_provider_repository,
    get_service_request_repository,
    get_user_repository,
)
from app.main import app
from app.repositories.providers import ProviderProfileExistsError
from app.repositories.users import DuplicateEmailError


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

    async def list_all(self, limit: int = 10_000) -> list[dict[str, Any]]:
        return list(self.by_id.values())[:limit]

    async def update_statistics(
        self, provider_id: str, statistics: dict[str, int | float]
    ) -> dict[str, Any] | None:
        provider = self.by_id.get(provider_id)
        if provider is not None:
            provider.update(statistics)
        return provider


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


def test_customer_and_provider_authenticated_api_flow() -> None:
    async def run_test() -> None:
        users = InMemoryUserRepository()
        providers = InMemoryProviderRepository()
        requests = InMemoryServiceRequestRepository()
        customers = InMemoryCustomerProfileRepository()
        interactions = InMemoryInteractionRepository()

        app.dependency_overrides[get_user_repository] = lambda: users
        app.dependency_overrides[get_provider_repository] = lambda: providers
        app.dependency_overrides[get_service_request_repository] = lambda: requests
        app.dependency_overrides[get_customer_profile_repository] = lambda: customers
        app.dependency_overrides[get_interaction_repository] = lambda: interactions

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
                    },
                )
                assert updated_profile.status_code == 200
                assert updated_profile.json()["city"] == "Kottawa"

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
                    json={"rating": 5},
                )
                assert rating.status_code == 200
                assert rating.json()["rating"] == 5
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
