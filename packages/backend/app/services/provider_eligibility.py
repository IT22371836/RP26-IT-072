from __future__ import annotations

import hashlib
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Iterable


ELIGIBILITY_VERSION = 1
RESEARCH_PIPELINE_TARGET = 1_000
RESEARCH_SELECTION_VERSION = "research-balanced-category-location-v1"
RESEARCH_SOURCE = "research_seed"
WEB_SOURCE = "web_registration"
LEGACY_SOURCE = "legacy_unknown"
PIPELINE_SOURCES = {RESEARCH_SOURCE, WEB_SOURCE}
WORKING_DAYS = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)


def has_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def c1_profile_ready(profile: dict[str, Any]) -> bool:
    return all(
        has_text(
            profile.get(field)
            or profile.get(
                {
                    "fullName": "provider_name",
                    "category": "category",
                    "district": "district",
                    "city": "city",
                }[field]
            )
        )
        for field in ("fullName", "category", "district", "city")
    )


def c2_profile_ready(profile: dict[str, Any]) -> bool:
    location = profile.get("location")
    if not isinstance(location, dict):
        return False
    try:
        latitude = float(location["latitude"])
        longitude = float(location["longitude"])
    except (KeyError, TypeError, ValueError):
        return False
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        return False
    working_hours = profile.get("workingHours") or profile.get("working_hours")
    if not isinstance(working_hours, dict):
        return False
    return all(
        isinstance(working_hours.get(day), dict)
        and isinstance(working_hours[day].get("isOpen"), bool)
        and isinstance(working_hours[day].get("start"), str)
        and isinstance(working_hours[day].get("end"), str)
        for day in WORKING_DAYS
    )


def standard_profile_ready(profile: dict[str, Any]) -> bool:
    """Require the profile fields shared by seeded and website registrations."""

    return all(
        has_text(profile.get(field))
        for field in ("nic", "phone", "preferredLanguage", "providerImage")
    )


def profile_source(profile: dict[str, Any]) -> str:
    explicit = str(profile.get("profileSource") or "").strip()
    if explicit in {RESEARCH_SOURCE, WEB_SOURCE, LEGACY_SOURCE}:
        return explicit
    if profile.get("researchSeed") is True:
        return RESEARCH_SOURCE
    return LEGACY_SOURCE


def runtime_pipeline_eligible(profile: dict[str, Any]) -> bool:
    eligibility = profile.get("pipelineEligibility")
    return (
        isinstance(eligibility, dict)
        and eligibility.get("version") == ELIGIBILITY_VERSION
        and eligibility.get("eligible") is True
        and eligibility.get("relationsValid") is True
        and eligibility.get("c1Ready") is True
        and eligibility.get("c2Ready") is True
        and eligibility.get("c4Ready") is True
        and eligibility.get("profileComplete") is True
        and eligibility.get("selectionVersion") == RESEARCH_SELECTION_VERSION
        and profile.get("verified") is True
        and profile_source(profile) in PIPELINE_SOURCES
        and (
            profile_source(profile) == WEB_SOURCE
            or eligibility.get("activeResearchBaseline") is True
        )
        and c1_profile_ready(profile)
        and c2_profile_ready(profile)
        and standard_profile_ready(profile)
    )


@dataclass(frozen=True)
class EligibleProviderPool:
    allowed_provider_ids: set[str]
    eligible_profiles: list[dict[str, Any]]
    research_count: int
    website_count: int


@dataclass(frozen=True)
class ResearchBaseline:
    provider_ids: set[str]
    category_quotas: dict[str, int]
    category_counts: dict[str, int]


def _selection_key(provider_id: str) -> str:
    return hashlib.sha256(
        f"{RESEARCH_SELECTION_VERSION}:{provider_id}".encode("utf-8")
    ).hexdigest()


def select_research_baseline(
    profiles: Iterable[dict[str, Any]],
    shared_provider_ids: set[str],
    target: int = RESEARCH_PIPELINE_TARGET,
) -> ResearchBaseline:
    """Select a deterministic category/location-balanced research baseline."""

    by_category: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    for profile in profiles:
        provider_id = str(
            profile.get("provider_id") or profile.get("id") or profile.get("uid") or ""
        ).strip()
        category = str(profile.get("category") or "").strip()
        if not provider_id or provider_id not in shared_provider_ids or not category:
            continue
        district = str(profile.get("district") or "UNKNOWN").strip() or "UNKNOWN"
        city = str(profile.get("city") or "UNKNOWN").strip() or "UNKNOWN"
        by_category[category].append((provider_id, district, city))

    categories = sorted(by_category)
    available = sum(len(items) for items in by_category.values())
    if target < 1 or target > available or not categories:
        raise ValueError(
            f"Research target {target} must be between 1 and available population {available}"
        )

    base, remainder = divmod(target, len(categories))
    quotas = {
        category: min(len(by_category[category]), base + (index < remainder))
        for index, category in enumerate(categories)
    }
    unassigned = target - sum(quotas.values())
    while unassigned:
        progressed = False
        for category in categories:
            if quotas[category] < len(by_category[category]):
                quotas[category] += 1
                unassigned -= 1
                progressed = True
                if not unassigned:
                    break
        if not progressed:
            raise ValueError("Research target cannot be distributed across categories")

    selected: set[str] = set()
    counts: dict[str, int] = {}
    for category in categories:
        locations: dict[tuple[str, str], list[str]] = defaultdict(list)
        for provider_id, district, city in by_category[category]:
            locations[(district, city)].append(provider_id)
        for provider_ids in locations.values():
            provider_ids.sort(key=_selection_key)
        location_keys = sorted(locations)
        offsets = {key: 0 for key in location_keys}
        while counts.get(category, 0) < quotas[category]:
            progressed = False
            for key in location_keys:
                offset = offsets[key]
                if offset >= len(locations[key]):
                    continue
                selected.add(locations[key][offset])
                offsets[key] += 1
                counts[category] = counts.get(category, 0) + 1
                progressed = True
                if counts[category] == quotas[category]:
                    break
            if not progressed:
                raise ValueError(f"Could not satisfy research quota for {category}")

    return ResearchBaseline(
        provider_ids=selected,
        category_quotas=quotas,
        category_counts=counts,
    )


def eligible_provider_pool(
    profiles: Iterable[dict[str, Any]], artifact_provider_ids: set[str]
) -> EligibleProviderPool:
    selected: dict[str, dict[str, Any]] = {}
    research_count = 0
    website_count = 0
    for profile in profiles:
        provider_id = str(
            profile.get("provider_id") or profile.get("id") or profile.get("uid") or ""
        ).strip()
        if not provider_id or not runtime_pipeline_eligible(profile):
            continue
        source = profile_source(profile)
        if source == RESEARCH_SOURCE:
            if provider_id not in artifact_provider_ids:
                continue
            research_count += 1
        elif source == WEB_SOURCE:
            if provider_id in artifact_provider_ids:
                continue
            website_count += 1
        else:
            continue
        selected[provider_id] = profile
    return EligibleProviderPool(
        allowed_provider_ids=set(selected),
        eligible_profiles=[selected[key] for key in sorted(selected)],
        research_count=research_count,
        website_count=website_count,
    )
