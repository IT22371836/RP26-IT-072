from datetime import UTC, datetime


class ServiceRequestInDB:
    """Represents a service request document stored in MongoDB `service_requests` collection.these are the columns saves in DB"""

    __slots__ = (
        "id",
        "service_type",
        "service_issue",
        "location",
        "date",
        "time",
        "service_env",
        "created_at",
    )

    def __init__(
        self,
        *,
        id: str,
        service_type: str,
        service_issue: str,
        location: dict,
        date: str,
        time: str,
        service_env: list[str],
        created_at: datetime | None = None,
    ) -> None:
        self.id = id
        self.service_type = service_type
        self.service_issue = service_issue
        self.location = location
        self.date = date
        self.time = time
        self.service_env = service_env
        self.created_at = created_at or datetime.now(UTC)
