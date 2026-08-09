from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.config import Settings


class FirebaseIdentityError(Exception):
    def __init__(self, message: str, *, reason: str = "invalid") -> None:
        super().__init__(message)
        self.reason = reason


class FirebaseIdentityConfigurationError(Exception):
    pass


@dataclass(frozen=True)
class VerifiedFirebaseIdentity:
    uid: str
    email: str
    email_verified: bool
    auth_time: int | None = None


class FirebaseTokenVerifier:
    """Verify client ID tokens with Firebase Admin in the trusted backend only."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def verify(
        self, id_token: str, *, require_verified_email: bool = True
    ) -> VerifiedFirebaseIdentity:
        project_id = self.settings.firebase_project_id
        if not project_id:
            raise FirebaseIdentityConfigurationError(
                "Firebase token verification is not configured"
            )
        try:
            import firebase_admin
            from firebase_admin import auth, credentials

            app_name = f"weda-auth-{project_id}"
            try:
                firebase_app = firebase_admin.get_app(app_name)
            except ValueError:
                credential = None
                if self.settings.firebase_credentials_path:
                    credential = credentials.Certificate(
                        str(self.settings.firebase_credentials_path)
                    )
                if credential is None:
                    firebase_app = firebase_admin.initialize_app(
                        options={"projectId": project_id},
                        name=app_name,
                    )
                else:
                    firebase_app = firebase_admin.initialize_app(
                        credential,
                        options={"projectId": project_id},
                        name=app_name,
                    )
            claims: dict[str, Any] = auth.verify_id_token(
                id_token,
                app=firebase_app,
                check_revoked=self.settings.firebase_check_revoked,
            )
        except FirebaseIdentityConfigurationError:
            raise
        except Exception as error:
            error_name = type(error).__name__
            reason = {
                "ExpiredIdTokenError": "expired",
                "RevokedIdTokenError": "revoked",
                "UserDisabledError": "disabled",
                "CertificateFetchError": "certificate_unavailable",
            }.get(error_name, "invalid")
            raise FirebaseIdentityError(
                "Firebase ID token verification failed", reason=reason
            ) from error

        uid = claims.get("uid") or claims.get("sub")
        email = claims.get("email")
        email_verified = claims.get("email_verified") is True
        if not isinstance(uid, str) or not uid:
            raise FirebaseIdentityError("Firebase ID token has no UID")
        if not isinstance(email, str) or not email.strip():
            raise FirebaseIdentityError("Firebase ID token has no email address")
        if require_verified_email and not email_verified:
            raise FirebaseIdentityError(
                "Firebase ID token must contain a verified email address"
            )
        auth_time = claims.get("auth_time")
        return VerifiedFirebaseIdentity(
            uid=uid,
            email=email.strip().lower(),
            email_verified=email_verified,
            auth_time=auth_time if isinstance(auth_time, int) else None,
        )
