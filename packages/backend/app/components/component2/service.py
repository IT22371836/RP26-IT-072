from __future__ import annotations

import math
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import requests

from app.components.component2.schemas import (
    Component2FilterRequest,
    Component2FilterResult,
    ServiceTime,
)


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_km = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    value = (
        math.sin(dphi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2.0) ** 2
    )
    return radius_km * 2.0 * math.atan2(math.sqrt(value), math.sqrt(1.0 - value))


def provider_availability(
    service_date: str,
    service_time: dict[str, str],
    working_hours: dict[str, Any],
) -> tuple[bool, str, str]:
    requested_date = datetime.strptime(service_date, "%Y-%m-%d")
    day_name = requested_date.strftime("%A")
    schedule = working_hours.get(day_name)
    if not isinstance(schedule, dict):
        return False, day_name, f"No working schedule set for {day_name}"
    if schedule.get("isOpen") is not True:
        return False, day_name, f"Provider does not work on {day_name}"
    try:
        provider_start = ServiceTime.parse(str(schedule.get("start", "")))
        provider_end = ServiceTime.parse(str(schedule.get("end", "")))
        request_start = ServiceTime.parse(service_time["start_time"])
        request_end = ServiceTime.parse(service_time["end_time"])
    except (KeyError, ValueError):
        return False, day_name, f"Invalid working-hours configuration for {day_name}"
    if provider_start <= request_start and request_end <= provider_end:
        return (
            True,
            day_name,
            f"Available on {day_name} ({schedule.get('start')} - {schedule.get('end')})",
        )
    return False, day_name, f"Outside working hours on {day_name}"


def _fetch_weather(
    latitude: float,
    longitude: float,
    *,
    timeout_seconds: float,
    retries: int,
) -> dict[str, Any] | None:
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
        "timezone": "auto",
    }
    for attempt in range(retries):
        try:
            response = requests.get(url, params=params, timeout=timeout_seconds)
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError):
            if attempt + 1 < retries:
                time.sleep(2**attempt)
    return None


def weather_analysis(
    data: dict[str, Any] | None,
    service_date: str,
    location_type: str,
) -> dict[str, str]:
    daily = data.get("daily") if isinstance(data, dict) else None
    if not isinstance(daily, dict) or service_date not in daily.get("time", []):
        return {
            "weather_summary": "Weather Data Unavailable",
            "overall_risk": "UNKNOWN",
            "recommendation": "Weather could not be evaluated; confirm conditions manually.",
        }
    index = daily["time"].index(service_date)
    max_temp = float(daily["temperature_2m_max"][index])
    min_temp = float(daily["temperature_2m_min"][index])
    rain_mm = float(daily["precipitation_sum"][index])
    raw_risk = "HIGH_RISK" if rain_mm > 15 else "MODERATE_RISK" if rain_mm > 5 else "LOW_RISK"
    normalized_type = location_type.strip().lower()
    if normalized_type == "indoor" and raw_risk == "HIGH_RISK":
        risk = "MODERATE_RISK"
        recommendation = "Heavy rain creates travel risk, but the indoor work site is protected."
    elif normalized_type == "indoor" and raw_risk != "HIGH_RISK":
        risk = "LOW_RISK"
        recommendation = "Indoor service can proceed; confirm travel conditions before departure."
    elif normalized_type == "indoor and outdoor" and raw_risk == "HIGH_RISK":
        risk = raw_risk
        recommendation = "Complete indoor work first and postpone exposed outdoor work."
    elif raw_risk == "HIGH_RISK":
        risk = raw_risk
        recommendation = "Heavy rain is forecast; reschedule or prepare suitable protection."
    elif raw_risk == "MODERATE_RISK":
        risk = raw_risk
        recommendation = "Moderate rain is forecast; use protective equipment for outdoor work."
    else:
        risk = raw_risk
        recommendation = "Weather conditions are suitable for the requested service."
    return {
        "weather_summary": (
            f"Date: {service_date}, Max Temp: {max_temp}°C, "
            f"Min Temp: {min_temp}°C, Rain: {rain_mm}mm"
        ),
        "overall_risk": risk,
        "recommendation": recommendation,
    }


class Component2FilteringService:
    def __init__(
        self,
        *,
        component_version: str,
        model_version: str,
        weather_timeout_seconds: float = 10,
        weather_retries: int = 3,
        weather_fetcher: Callable[..., dict[str, Any] | None] = _fetch_weather,
    ) -> None:
        self.component_version = component_version
        self.model_version = model_version
        self.weather_timeout_seconds = weather_timeout_seconds
        self.weather_retries = weather_retries
        self.weather_fetcher = weather_fetcher

    def filter(
        self,
        payload: Component2FilterRequest,
        customer: dict[str, Any],
        providers: dict[str, dict[str, Any]],
        *,
        top_k: int = 10,
    ) -> Component2FilterResult:
        location = customer.get("location")
        if not isinstance(location, dict):
            raise ValueError("Customer location is required for Component 2")
        customer_lat = float(location["latitude"])
        customer_lon = float(location["longitude"])
        service_date = payload.service_date.isoformat()
        weather = self.weather_fetcher(
            customer_lat,
            customer_lon,
            timeout_seconds=self.weather_timeout_seconds,
            retries=self.weather_retries,
        )
        weather_result = weather_analysis(weather, service_date, payload.location_type)
        evaluated: list[dict[str, Any]] = []
        for provider_id in payload.results["provider_ids"]:
            provider = providers.get(provider_id)
            if provider is None:
                evaluated.append(
                    {
                        "request_id": payload.request_id,
                        "user_id": payload.user_id,
                        "provider_id": provider_id,
                        "provider_name": "Unknown provider",
                        "distance_km": None,
                        "is_available": False,
                        "working_hours_status": "Provider record not found in Firebase",
                        "location_type": payload.location_type,
                        "weather_risk": weather_result["overall_risk"],
                        "recommendation": weather_result["recommendation"],
                    }
                )
                continue
            provider_location = provider.get("location")
            if not isinstance(provider_location, dict):
                distance = None
                available, day, reason = False, "N/A", "Provider location is missing"
            else:
                latitude = float(provider_location["latitude"])
                longitude = float(provider_location["longitude"])
                distance = haversine_distance(customer_lat, customer_lon, latitude, longitude)
                available, day, reason = provider_availability(
                    service_date,
                    payload.service_time.model_dump(),
                    provider.get("workingHours", {}),
                )
            evaluated.append(
                {
                    "request_id": payload.request_id,
                    "user_id": payload.user_id,
                    "provider_id": provider_id,
                    "provider_name": provider.get("fullName", provider_id),
                    "provider_location": provider_location,
                    "distance_km": round(distance, 2) if distance is not None else None,
                    "service_day": day,
                    "is_available": available,
                    "working_hours_status": reason,
                    "location_type": payload.location_type,
                    "weather_risk": weather_result["overall_risk"],
                    "recommendation": weather_result["recommendation"],
                }
            )
        available = sorted(
            (item for item in evaluated if item["is_available"] is True),
            key=lambda item: (
                float("inf") if item["distance_km"] is None else item["distance_km"],
                item["provider_id"],
            ),
        )[:top_k]
        output = {
            "provider_ids": [item["provider_id"] for item in available],
            "evaluated_providers": available,
            "weather_risk": weather_result["overall_risk"],
            "recommendation": weather_result["recommendation"],
            "weather_summary": weather_result["weather_summary"],
            "evaluated_at": datetime.now(UTC).isoformat(),
        }
        return Component2FilterResult(
            output_results=output,
            all_evaluated_providers=evaluated,
            component_version=self.component_version,
            model_version=self.model_version,
        )
