import asyncio
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import firebase_admin
import jwt
import pytest
from firebase_admin import auth as firebase_auth
from httpx import ASGITransport, AsyncClient

from app.api.auth import account_link_service, auth_service
from app.api.dependencies import get_user_repository
from app.core.config import Settings, get_settings
from app.core.security import create_access_token, hash_password, verify_password
from app.main import app
from app.repositories.users import FirebaseLinkConflictError
from app.schemas.auth import FirebaseAccountLinkRequest, PasswordChangeRequest
from app.schemas.common import UserRole
from app.services.account_link import (
    AccountAlreadyLinkedError,
    AccountLinkForbiddenError,
    AccountLinkService,
    AmbiguousAccountLinkError,
)
from app.services.auth import AuthService
from app.services.firebase_identity import FirebaseTokenVerifier, VerifiedFirebaseIdentity

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def settings(**updates: Any) -> Settings:
    values = {
        "jwt_secret_key": "phase5-test-secret-key-that-is-long-enough",
        "firebase_project_id": "phase5-test-project",
    }
    values.update(updates)
    return Settings(_env_file=None, **values)


class FakeFirebaseVerifier:
    def __init__(self, identity: VerifiedFirebaseIdentity) -> None:
        self.identity = identity
        self.tokens: list[str] = []

    def verify(self, token: str) -> VerifiedFirebaseIdentity:
        self.tokens.append(token)
        return self.identity


class TransitionUserRepository:
    def __init__(self, users: list[dict[str, Any]]) -> None:
        self.users = {str(user["user_id"]): deepcopy(user) for user in users}

    async def find_by_id(self, user_id: str) -> dict[str, Any] | None:
        user = self.users.get(user_id)
        return deepcopy(user) if user else None

    async def find_by_email(self, email: str) -> dict[str, Any] | None:
        matches = await self.find_all_by_email(email)
        return matches[0] if matches else None

    async def find_all_by_email(
        self, email: str, *, limit: int = 2
    ) -> list[dict[str, Any]]:
        normalized = email.strip().lower()
        return [
            deepcopy(user)
            for user in self.users.values()
            if str(user.get("email", "")).strip().lower() == normalized
        ][:limit]

    async def find_by_firebase_uid(self, uid: str) -> dict[str, Any] | None:
        return next(
            (
                deepcopy(user)
                for user in self.users.values()
                if user.get("legacy", {}).get("firebase_uid") == uid
            ),
            None,
        )

    async def link_firebase_identity(
        self,
        user_id: str,
        firebase_uid: str,
        firebase_email: str,
        hashed_password: str,
        linked_at: datetime,
        auth_version: int,
    ) -> dict[str, Any]:
        if any(
            user.get("legacy", {}).get("firebase_uid") == firebase_uid
            for user in self.users.values()
        ):
            raise FirebaseLinkConflictError
        user = self.users[user_id]
        if user.get("legacy", {}).get("firebase_uid"):
            raise FirebaseLinkConflictError
        user.setdefault("legacy", {})["firebase_uid"] = firebase_uid
        user["hashed_password"] = hashed_password
        user["auth_version"] = auth_version
        user.setdefault("auth_transition", {}).update(
            {
                "firebase_email_at_link": firebase_email,
                "firebase_linked_at": linked_at,
                "password_established_at": linked_at,
            }
        )
        user["updated_at"] = linked_at
        return deepcopy(user)

    async def change_password(
        self,
        user_id: str,
        hashed_password: str,
        changed_at: datetime,
        current_auth_version: int,
    ) -> dict[str, Any] | None:
        user = self.users.get(user_id)
        if user is None or int(user.get("auth_version", 1)) != current_auth_version:
            return None
        user["hashed_password"] = hashed_password
        user["auth_version"] = current_auth_version + 1
        user.setdefault("auth_transition", {})["password_changed_at"] = changed_at
        user["updated_at"] = changed_at
        return deepcopy(user)


def user_document(
    *,
    user_id: str = "U1",
    email: str = "linked@example.com",
    role: str = "customer",
    is_active: bool = True,
) -> dict[str, Any]:
    now = datetime(2026, 8, 5, tzinfo=UTC)
    return {
        "user_id": user_id,
        "email": email,
        "full_name": "Linked User",
        "role": role,
        "is_active": is_active,
        "hashed_password": hash_password("OldPassword123!"),
        "auth_version": 1,
        "created_at": now,
        "unknown_existing_field": {"nested": [False, None, 0, ""]},
    }


def link_payload() -> FirebaseAccountLinkRequest:
    return FirebaseAccountLinkRequest(
        firebase_id_token="x" * 200,
        new_password="NewBackendPassword123!",
    )


def test_one_time_link_verifies_firebase_identity_and_preserves_user_fields() -> None:
    async def run_test() -> None:
        repository = TransitionUserRepository([user_document()])
        verifier = FakeFirebaseVerifier(
            VerifiedFirebaseIdentity(
                uid="firebase-uid-1",
                email="linked@example.com",
                email_verified=True,
            )
        )
        service = AccountLinkService(repository, settings(), verifier)  # type: ignore[arg-type]

        response = await service.link(link_payload())
        stored = repository.users["U1"]

        assert verifier.tokens == ["x" * 200]
        assert response.user.user_id == "U1"
        assert response.access_token
        assert stored["legacy"]["firebase_uid"] == "firebase-uid-1"
        assert stored["auth_version"] == 2
        assert verify_password("NewBackendPassword123!", stored["hashed_password"])
        assert stored["unknown_existing_field"] == {"nested": [False, None, 0, ""]}
        assert stored["auth_transition"]["firebase_email_at_link"] == (
            "linked@example.com"
        )

        with pytest.raises(AccountAlreadyLinkedError):
            await service.link(link_payload())

    asyncio.run(run_test())


def test_firebase_admin_verification_uses_project_and_revocation_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    initialized: list[dict[str, Any]] = []
    verified: list[dict[str, Any]] = []
    firebase_app = object()

    def missing_app(_name: str) -> None:
        raise ValueError

    def initialize_app(
        *, options: dict[str, Any], name: str
    ) -> object:
        initialized.append({"options": options, "name": name})
        return firebase_app

    def verify_id_token(
        token: str,
        *,
        app: object,
        check_revoked: bool,
    ) -> dict[str, Any]:
        verified.append(
            {"token": token, "app": app, "check_revoked": check_revoked}
        )
        return {
            "uid": "firebase-uid",
            "email": " USER@EXAMPLE.COM ",
            "email_verified": True,
            "auth_time": 123,
        }

    monkeypatch.setattr(firebase_admin, "get_app", missing_app)
    monkeypatch.setattr(firebase_admin, "initialize_app", initialize_app)
    monkeypatch.setattr(firebase_auth, "verify_id_token", verify_id_token)

    identity = FirebaseTokenVerifier(settings(firebase_check_revoked=True)).verify(
        "verified-token"
    )

    assert initialized == [
        {
            "options": {"projectId": "phase5-test-project"},
            "name": "weda-auth-phase5-test-project",
        }
    ]
    assert verified == [
        {
            "token": "verified-token",
            "app": firebase_app,
            "check_revoked": True,
        }
    ]
    assert identity.uid == "firebase-uid"
    assert identity.email == "user@example.com"
    assert identity.email_verified is True


def test_production_settings_require_secure_cookie_and_firebase_project() -> None:
    base = {
        "_env_file": None,
        "app_env": "production",
        "jwt_secret_key": "production-secret-key-that-is-long-enough",
    }
    with pytest.raises(ValueError, match="AUTH_COOKIE_ENABLED"):
        Settings(**base)
    with pytest.raises(ValueError, match="AUTH_COOKIE_SECURE"):
        Settings(**base, auth_cookie_enabled=True)
    with pytest.raises(ValueError, match="FIREBASE_PROJECT_ID"):
        Settings(
            **base,
            auth_cookie_enabled=True,
            auth_cookie_secure=True,
        )
    with pytest.raises(ValueError, match="FIREBASE_STORAGE_BUCKET"):
        Settings(
            **base,
            auth_cookie_enabled=True,
            auth_cookie_secure=True,
            firebase_project_id="production-project",
        )

    production = Settings(
        **base,
        auth_cookie_enabled=True,
        auth_cookie_secure=True,
        firebase_project_id="production-project",
        firebase_storage_bucket="production-project.firebasestorage.app",
    )
    assert production.auth_cookie_samesite == "lax"


def test_link_rejects_duplicate_email_inactive_and_admin_accounts() -> None:
    async def run_test() -> None:
        identity = VerifiedFirebaseIdentity(
            uid="firebase-uid",
            email="duplicate@example.com",
            email_verified=True,
        )
        duplicate_repository = TransitionUserRepository(
            [
                user_document(user_id="U1", email="duplicate@example.com"),
                user_document(user_id="U2", email="Duplicate@Example.com"),
            ]
        )
        with pytest.raises(AmbiguousAccountLinkError):
            await AccountLinkService(
                duplicate_repository,
                settings(),
                FakeFirebaseVerifier(identity),  # type: ignore[arg-type]
            ).link(link_payload())
        assert all("legacy" not in user for user in duplicate_repository.users.values())

        for document in (
            user_document(email="duplicate@example.com", is_active=False),
            user_document(email="duplicate@example.com", role="admin"),
        ):
            with pytest.raises(AccountLinkForbiddenError):
                await AccountLinkService(
                    TransitionUserRepository([document]),
                    settings(),
                    FakeFirebaseVerifier(identity),  # type: ignore[arg-type]
                ).link(link_payload())

    asyncio.run(run_test())


def test_password_change_increments_auth_version_and_invalidates_old_token() -> None:
    async def run_test() -> None:
        repository = TransitionUserRepository([user_document()])
        config = settings()
        service = AuthService(repository, config)  # type: ignore[arg-type]
        old_token, _ = create_access_token(
            "U1", UserRole.CUSTOMER, config, auth_version=1
        )

        response = await service.change_password(
            "U1",
            PasswordChangeRequest(
                current_password="OldPassword123!",
                new_password="ChangedPassword123!",
            ),
        )
        assert response.access_token
        assert repository.users["U1"]["auth_version"] == 2

        app.dependency_overrides[get_settings] = lambda: config
        app.dependency_overrides[get_user_repository] = lambda: repository
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                old_response = await client.get(
                    "/api/v1/auth/me",
                    headers={"Authorization": f"Bearer {old_token}"},
                )
                new_response = await client.get(
                    "/api/v1/auth/me",
                    headers={"Authorization": f"Bearer {response.access_token}"},
                )
        finally:
            app.dependency_overrides.clear()
        assert old_response.status_code == 401
        assert new_response.status_code == 200

    asyncio.run(run_test())


def test_cookie_transport_is_http_only_and_authenticates_without_browser_token() -> None:
    async def run_test() -> None:
        config = settings(
            auth_cookie_enabled=True,
            auth_cookie_secure=True,
            auth_cookie_samesite="lax",
        )
        repository = TransitionUserRepository([user_document()])
        service = AuthService(repository, config)  # type: ignore[arg-type]
        app.dependency_overrides[get_settings] = lambda: config
        app.dependency_overrides[get_user_repository] = lambda: repository
        app.dependency_overrides[auth_service] = lambda: service
        try:
            # HTTPS is required because the test intentionally exercises a Secure cookie.
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport,
                base_url="https://testserver",
            ) as client:
                login_response = await client.post(
                    "/api/v1/auth/login",
                    json={
                        "email": "linked@example.com",
                        "password": "OldPassword123!",
                    },
                )
                me_response = await client.get("/api/v1/auth/me")
                logout_response = await client.post("/api/v1/auth/logout")
        finally:
            app.dependency_overrides.clear()

        assert login_response.status_code == 200
        assert login_response.json()["access_token"] is None
        assert login_response.json()["token_transport"] == "cookie"
        cookie = login_response.headers["set-cookie"].lower()
        assert "httponly" in cookie
        assert "secure" in cookie
        assert "samesite=lax" in cookie
        assert me_response.status_code == 200
        assert logout_response.status_code == 204
        assert "max-age=0" in logout_response.headers["set-cookie"].lower()

    asyncio.run(run_test())


def test_disabled_expired_and_wrong_role_tokens_are_rejected() -> None:
    async def request_status(document: dict[str, Any], token: str) -> int:
        config = settings()
        repository = TransitionUserRepository([document])
        app.dependency_overrides[get_settings] = lambda: config
        app.dependency_overrides[get_user_repository] = lambda: repository
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                response = await client.get(
                    "/api/v1/auth/me",
                    headers={"Authorization": f"Bearer {token}"},
                )
                return response.status_code
        finally:
            app.dependency_overrides.clear()

    config = settings()
    valid_token, _ = create_access_token(
        "U1", UserRole.CUSTOMER, config, auth_version=1
    )
    wrong_role_token, _ = create_access_token(
        "U1", UserRole.PROVIDER, config, auth_version=1
    )
    now = datetime.now(UTC)
    expired_token = jwt.encode(
        {
            "sub": "U1",
            "role": "customer",
            "ver": 1,
            "iat": now - timedelta(hours=2),
            "exp": now - timedelta(hours=1),
        },
        config.jwt_secret_key,
        algorithm=config.jwt_algorithm,
    )

    assert asyncio.run(request_status(user_document(is_active=False), valid_token)) == 401
    assert asyncio.run(request_status(user_document(), expired_token)) == 401
    assert asyncio.run(request_status(user_document(), wrong_role_token)) == 401


def test_firebase_link_endpoint_uses_verified_service_and_returns_backend_token() -> None:
    async def run_test() -> None:
        repository = TransitionUserRepository([user_document()])
        verifier = FakeFirebaseVerifier(
            VerifiedFirebaseIdentity(
                uid="firebase-endpoint-uid",
                email="linked@example.com",
                email_verified=True,
            )
        )
        config = settings()
        service = AccountLinkService(repository, config, verifier)  # type: ignore[arg-type]
        app.dependency_overrides[get_settings] = lambda: config
        app.dependency_overrides[account_link_service] = lambda: service
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                response = await client.post(
                    "/api/v1/auth/link/firebase",
                    json={
                        "firebase_id_token": "z" * 200,
                        "new_password": "EstablishedPassword123!",
                    },
                )
        finally:
            app.dependency_overrides.clear()
        assert response.status_code == 200
        assert response.json()["user"]["user_id"] == "U1"
        assert response.json()["access_token"]
        assert verifier.tokens == ["z" * 200]

    asyncio.run(run_test())


def test_frontend_contains_no_hard_coded_administrator_credentials() -> None:
    frontend_source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((REPOSITORY_ROOT / "WEB" / "src").rglob("*"))
        if path.suffix in {".ts", ".tsx"}
    )
    assert "Admin@123" not in frontend_source
    assert "admin@gmail.com" not in frontend_source
    assert "ADMIN_EMAIL" not in frontend_source
    assert "service_account" not in frontend_source.lower()
    assert "private_key" not in frontend_source.lower()
