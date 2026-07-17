import asyncio
from typing import Any

from httpx import ASGITransport, AsyncClient

from app.api.dependencies import (
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

        app.dependency_overrides[get_user_repository] = lambda: users
        app.dependency_overrides[get_provider_repository] = lambda: providers
        app.dependency_overrides[get_service_request_repository] = lambda: requests

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                customer, customer_headers = await register_and_login(
                    client, "customer", "customer-flow@example.com"
                )

                me = await client.get("/api/v1/auth/me", headers=customer_headers)
                assert me.status_code == 200
                assert me.json()["user_id"] == customer["user_id"]

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
