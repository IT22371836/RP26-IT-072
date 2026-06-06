"""
Provider Matching Service
Filters providers from the local JSON dataset based on:
  1. Service type match
  2. Working day compatibility (weekday / weekend / whole week)
  3. Available hours overlap with the requested time
Matched providers are sorted by distance (closest first) using the Haversine formula.
"""
from __future__ import annotations

import json
import logging
import math
from datetime import date as date_type
from pathlib import Path

logger = logging.getLogger(__name__)

_PROVIDERS_PATH = Path(__file__).parent.parent / "data" / "providers.json"

# Day-of-week: 0=Monday … 4=Friday, 5=Saturday, 6=Sunday
_WEEKDAY_INDICES = {0, 1, 2, 3, 4}
_WEEKEND_INDICES = {5, 6}


def _load_providers() -> list[dict]:
    with open(_PROVIDERS_PATH, encoding="utf-8") as f:
        return json.load(f)


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two coordinates in kilometres."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return R * 2 * math.asin(math.sqrt(a))


def _parse_hour_12(token: str) -> int:
    """Convert '8am', '5pm', '12pm', '12am' → 24-hour integer."""
    token = token.strip().lower()
    if token.endswith("am"):
        h = int(token[:-2])
        return 0 if h == 12 else h
    elif token.endswith("pm"):
        h = int(token[:-2])
        return h if h == 12 else h + 12
    raise ValueError(f"Cannot parse hour token: {token!r}")


def _is_working_day(working_days: str, date_str: str) -> bool:
    weekday = date_type.fromisoformat(date_str).weekday()
    wd = working_days.lower().strip()
    if wd == "whole week":
        return True
    if wd == "weekdays only":
        return weekday in _WEEKDAY_INDICES
    if wd == "weekends only":
        return weekday in _WEEKEND_INDICES
    logger.warning("[ProviderMatching] Unknown workingDays value: %r", working_days)
    return False


def _is_within_hours(available_hours: str, request_time: str) -> bool:
    """
    Returns True if the requested time falls within the provider's hours.
    E.g. available_hours='8am to 5pm', request_time='14:30' → True
    """
    parts = available_hours.lower().split(" to ")
    if len(parts) != 2:
        logger.warning("[ProviderMatching] Cannot parse hours: %r", available_hours)
        return False
    try:
        start_h = _parse_hour_12(parts[0])
        end_h = _parse_hour_12(parts[1])
    except ValueError as exc:
        logger.warning("[ProviderMatching] Hour parse error: %s", exc)
        return False
    req_h = int(request_time.split(":")[0])
    return start_h <= req_h < end_h


def find_matching_providers(
    service_type: str,
    date: str,
    time: str,
    user_lat: float,
    user_lon: float,
) -> list[dict]:
    """
    Returns a list of providers that match all three criteria, sorted by
    distance from the user's location (nearest first).

    Each item in the returned list is a plain dict with keys:
      provider_id, first_name, last_name, service_type,
      work_location, home_address, available_hours, working_days, distance_km
    """
    providers = _load_providers()
    matched: list[dict] = []

    logger.info(
        "[ProviderMatching] Matching providers | service_type=%s date=%s time=%s "
        "user_lat=%s user_lon=%s total_providers=%d",
        service_type,
        date,
        time,
        user_lat,
        user_lon,
        len(providers),
    )

    for p in providers:
        pid = p["providerID"]

        # 1 — Service type (case-insensitive)
        if p["serviceType"].lower() != service_type.lower():
            continue

        # 2 — Working day
        if not _is_working_day(p["workingDays"], date):
            logger.debug(
                "[ProviderMatching] %s excluded — workingDays=%r does not cover date=%s",
                pid,
                p["workingDays"],
                date,
            )
            continue

        # 3 — Available hours
        if not _is_within_hours(p["normalAvailableHours"], time):
            logger.debug(
                "[ProviderMatching] %s excluded — hours=%r do not cover time=%s",
                pid,
                p["normalAvailableHours"],
                time,
            )
            continue

        dist_km = round(
            _haversine_km(
                user_lat,
                user_lon,
                p["providersWorkLocation"]["latitude"],
                p["providersWorkLocation"]["longitude"],
            ),
            1,
        )

        matched.append(
            {
                "provider_id": pid,
                "first_name": p["providerFirstName"],
                "last_name": p["providerLastName"],
                "service_type": p["serviceType"],
                "work_location": p["providersWorkLocation"],
                "home_address": p["providersHomeAddress"],
                "available_hours": p["normalAvailableHours"],
                "working_days": p["workingDays"],
                "distance_km": dist_km,
            }
        )

    matched.sort(key=lambda x: x["distance_km"])

    logger.info(
        "[ProviderMatching] %d provider(s) matched for service_type=%s date=%s time=%s",
        len(matched),
        service_type,
        date,
        time,
    )
    return matched
