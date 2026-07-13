import asyncio
from typing import Any

from app.core.config import Settings
from app.repositories.users import DuplicateEmailError
from app.schemas.auth import CustomerRegistration, LoginRequest
from app.schemas.common import UserRole
from app.services.auth import AuthService, InvalidCredentialsError


class FakeUserRepository:
    def __init__(self) -> None:
        self.users: dict[str, dict[str, Any]] = {}

    async def create(self, document: dict[str, Any]) -> dict[str, Any]:
        if document["email"] in self.users:
            raise DuplicateEmailError
        self.users[document["email"]] = document
        return document

    async def find_by_email(self, email: str) -> dict[str, Any] | None:
        return self.users.get(email)


def test_register_and_login_customer() -> None:
    async def run_test() -> None:
        repository = FakeUserRepository()
        service = AuthService(
            repository,  # type: ignore[arg-type]
            Settings(
                mongodb_uri="mongodb://localhost:27017",
                mongodb_database="test_database",
                jwt_secret_key="test-secret-that-is-long-enough-for-tests",
            ),
        )
        registration = CustomerRegistration(
            email="Customer@Example.com",
            password="StrongPassword123!",
            full_name="Test Customer",
        )

        user = await service.register(registration, UserRole.CUSTOMER)
        token = await service.login(
            LoginRequest(email="customer@example.com", password="StrongPassword123!")
        )

        assert user.user_id.startswith("U")
        assert user.role is UserRole.CUSTOMER
        assert token.user.user_id == user.user_id
        assert token.access_token
        assert repository.users["customer@example.com"]["hashed_password"] != registration.password

    asyncio.run(run_test())


def test_login_rejects_incorrect_password() -> None:
    async def run_test() -> None:
        repository = FakeUserRepository()
        service = AuthService(
            repository,  # type: ignore[arg-type]
            Settings(
                mongodb_uri="mongodb://localhost:27017",
                mongodb_database="test_database",
                jwt_secret_key="test-secret-that-is-long-enough-for-tests",
            ),
        )
        await service.register(
            CustomerRegistration(
                email="customer@example.com",
                password="StrongPassword123!",
                full_name="Test Customer",
            ),
            UserRole.CUSTOMER,
        )

        try:
            await service.login(
                LoginRequest(email="customer@example.com", password="wrong-password")
            )
        except InvalidCredentialsError:
            return
        raise AssertionError("incorrect password was accepted")

    asyncio.run(run_test())
