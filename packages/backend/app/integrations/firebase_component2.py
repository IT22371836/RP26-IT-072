from __future__ import annotations

import asyncio
from copy import deepcopy
from typing import Any

from app.core.config import Settings


class FirebaseComponent2Error(RuntimeError):
    pass


class FirebaseRequestConflictError(FirebaseComponent2Error):
    pass


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
            await asyncio.to_thread(self._reference(".info/connected").get)
        except Exception:
            return False
        return True

    async def get_customer(self, firebase_uid: str) -> dict[str, Any] | None:
        value = await asyncio.to_thread(self._reference(f"customers/{firebase_uid}").get)
        return value if isinstance(value, dict) else None

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
