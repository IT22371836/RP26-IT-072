from datetime import UTC, datetime
from typing import Literal

UserRole = Literal["customer", "provider"]


class UserInDB:
    """Represents a user document stored in the MongoDB `users` collection."""

    __slots__ = (
        "id",
        "email",
        "role",
        "full_name",
        "phone",
        "password_hash",
        "created_at",
        # provider-specific
        "business_name",
        "service_types",
        "address",
    )

    def __init__(
        self,
        *,
        id: str,
        email: str,
        role: UserRole,
        full_name: str,
        password_hash: str,
        phone: str | None = None,
        business_name: str | None = None,
        service_types: list[str] | None = None,
        address: str | None = None,
        created_at: datetime | None = None,
    ) -> None:
        self.id = id
        self.email = email
        self.role = role
        self.full_name = full_name
        self.password_hash = password_hash
        self.phone = phone
        self.business_name = business_name
        self.service_types = service_types or []
        self.address = address
        self.created_at = created_at or datetime.now(UTC)

    @classmethod
    def from_doc(cls, doc: dict) -> "UserInDB":
        return cls(
            id=str(doc["_id"]),
            email=doc["email"],
            role=doc["role"],
            full_name=doc["full_name"],
            password_hash=doc["password_hash"],
            phone=doc.get("phone"),
            business_name=doc.get("business_name"),
            service_types=doc.get("service_types", []),
            address=doc.get("address"),
            created_at=doc.get("created_at"),
        )

    def to_doc(self) -> dict:
        doc: dict = {
            "email": self.email,
            "role": self.role,
            "full_name": self.full_name,
            "password_hash": self.password_hash,
            "created_at": self.created_at,
        }
        if self.phone is not None:
            doc["phone"] = self.phone
        if self.business_name is not None:
            doc["business_name"] = self.business_name
        if self.service_types:
            doc["service_types"] = self.service_types
        if self.address is not None:
            doc["address"] = self.address
        return doc
