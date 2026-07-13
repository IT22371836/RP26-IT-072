from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4


class UserRole(StrEnum):
    CUSTOMER = "customer"
    PROVIDER = "provider"
    ADMIN = "admin"


class Urgency(StrEnum):
    NORMAL = "normal"
    URGENT = "urgent"
    EMERGENCY = "emergency"


def new_public_id(prefix: str) -> str:
    """Create an opaque, collision-resistant ID while preserving pipeline prefixes."""

    return f"{prefix}{uuid4().hex[:12].upper()}"


def utc_now() -> datetime:
    return datetime.now(UTC)
