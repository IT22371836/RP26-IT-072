import re

PROVIDER_ID_PATTERN = r"^(?:P[A-Z0-9]+|[A-Za-z0-9_-]{20,128})$"


def is_supported_provider_id(value: str) -> bool:
    """Accept canonical research IDs and case-sensitive Firebase Auth UIDs."""

    return re.fullmatch(PROVIDER_ID_PATTERN, value) is not None
