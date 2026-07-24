"""
Weather Risk Advisory Service

Classifies weather conditions against service-type sensitivity profiles
to produce actionable risk advisories and suggest better scheduling windows.

The classifier uses a rule-based weighted scoring model whose thresholds are
derived from domain knowledge for each service type.  The score (0–100) maps to
four risk levels: SAFE · MODERATE · HIGH · EXTREME.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date as date_type, timedelta
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from app.services.weather_service import WeatherInfo

logger = logging.getLogger(__name__)

RiskLevel = Literal["SAFE", "MODERATE", "HIGH", "EXTREME"]

# ── Service-type sensitivity profiles ────────────────────────────────────────
# Each profile encodes the weather thresholds at which risk escalates for that
# service type.  Higher thresholds = less sensitive to bad weather.
_SENSITIVITY: dict[str, dict] = {
    "electrical": {
        # Even small amounts of rain create electrocution risk outdoors
        "precip_mm_moderate": 0.2,
        "precip_mm_high": 1.0,
        "precip_prob_moderate": 25,
        "precip_prob_high": 50,
        "wind_moderate": 30,
        "wind_high": 50,
        "dangerous_codes": {95, 96, 99},  # thunderstorms
    },
    "painting": {
        # Paint adhesion is ruined by moisture; high wind spreads paint
        "precip_mm_moderate": 0.1,
        "precip_mm_high": 0.5,
        "precip_prob_moderate": 20,
        "precip_prob_high": 40,
        "wind_moderate": 20,
        "wind_high": 35,
        "dangerous_codes": {95, 96, 99, 65, 63},  # heavy/moderate rain
    },
    "carpentry": {
        "precip_mm_moderate": 1.0,
        "precip_mm_high": 3.0,
        "precip_prob_moderate": 40,
        "precip_prob_high": 65,
        "wind_moderate": 35,
        "wind_high": 55,
        "dangerous_codes": {95, 96, 99},
    },
    "plumbing": {
        "precip_mm_moderate": 2.0,
        "precip_mm_high": 5.0,
        "precip_prob_moderate": 50,
        "precip_prob_high": 75,
        "wind_moderate": 40,
        "wind_high": 60,
        "dangerous_codes": {95, 96, 99},
    },
    "cleaning": {
        # Outdoor cleaning is least sensitive; heavy rain washes surfaces anyway
        "precip_mm_moderate": 5.0,
        "precip_mm_high": 10.0,
        "precip_prob_moderate": 70,
        "precip_prob_high": 90,
        "wind_moderate": 50,
        "wind_high": 70,
        "dangerous_codes": {95, 96, 99},
    },
}

_DEFAULT_PROFILE = _SENSITIVITY["plumbing"]

_RECOMMENDATION: dict[RiskLevel, str] = {
    "SAFE": "Conditions look good. No weather concerns for your scheduled service.",
    "MODERATE": (
        "Some weather concerns detected. Confirm the provider is aware and has "
        "suitable equipment for these conditions."
    ),
    "HIGH": (
        "Significant weather risk. Consider rescheduling or verify the provider "
        "can safely handle these conditions."
    ),
    "EXTREME": (
        "Dangerous weather conditions. Strongly recommend rescheduling to one of "
        "the safer time windows shown below."
    ),
}


@dataclass
class SuggestedWindow:
    date: str
    time: str
    condition: str
    temperature_c: float
    precipitation_probability: int
    risk_level: RiskLevel


@dataclass
class WeatherRiskAdvisory:
    risk_level: RiskLevel
    risk_score: float
    risk_reasons: list[str]
    recommendation: str
    suggested_windows: list[SuggestedWindow] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "risk_level": self.risk_level,
            "risk_score": round(self.risk_score, 1),
            "risk_reasons": self.risk_reasons,
            "recommendation": self.recommendation,
            "suggested_windows": [
                {
                    "date": w.date,
                    "time": w.time,
                    "condition": w.condition,
                    "temperature_c": w.temperature_c,
                    "precipitation_probability": w.precipitation_probability,
                    "risk_level": w.risk_level,
                }
                for w in self.suggested_windows
            ],
        }


# ── Internal helpers ─────────────────────────────────────────────────────────

def _get_risk_level(score: float) -> RiskLevel:
    if score < 20:
        return "SAFE"
    if score < 50:
        return "MODERATE"
    if score < 75:
        return "HIGH"
    return "EXTREME"


def _score_weather(weather: "WeatherInfo", service_type: str) -> tuple[float, list[str]]:
    """
    Compute a risk score (0–100) and reasons list for the given weather and
    service type.  Higher score = worse conditions.
    """
    profile = _SENSITIVITY.get(service_type.lower(), _DEFAULT_PROFILE)
    score = 0.0
    reasons: list[str] = []

    # Dangerous WMO weather codes (thunderstorms, violent rain, etc.)
    if weather.weather_code in profile["dangerous_codes"]:
        score += 60
        reasons.append(f"Dangerous weather detected: {weather.condition}")

    # Precipitation amount
    if weather.precipitation_mm >= profile["precip_mm_high"]:
        score += 25
        reasons.append(f"Heavy precipitation expected ({weather.precipitation_mm:.1f} mm)")
    elif weather.precipitation_mm >= profile["precip_mm_moderate"]:
        score += 12
        reasons.append(f"Moderate precipitation expected ({weather.precipitation_mm:.1f} mm)")

    # Precipitation probability
    if weather.precipitation_probability >= profile["precip_prob_high"]:
        score += 20
        reasons.append(f"High rain probability ({weather.precipitation_probability}%)")
    elif weather.precipitation_probability >= profile["precip_prob_moderate"]:
        score += 8
        reasons.append(f"Elevated rain probability ({weather.precipitation_probability}%)")

    # Wind speed
    if weather.wind_speed_kmh >= profile["wind_high"]:
        score += 15
        reasons.append(f"Strong winds ({weather.wind_speed_kmh:.0f} km/h)")
    elif weather.wind_speed_kmh >= profile["wind_moderate"]:
        score += 6
        reasons.append(f"Moderate winds ({weather.wind_speed_kmh:.0f} km/h)")

    return min(score, 100.0), reasons


async def _find_alternative_windows(
    service_type: str,
    latitude: float,
    longitude: float,
    requested_date: str,
    requested_hour: int,
    current_score: float,
    max_windows: int = 3,
) -> list[SuggestedWindow]:
    """
    Scan hourly forecast for the requested date + the next 2 days and return
    up to max_windows slots whose risk score is lower than current_score.

    One suggestion per day is surfaced to spread options across the week.
    Only reasonable service hours (07:00–19:00) are considered.
    """
    from app.services.weather_service import get_hourly_forecast_range

    end_date = (date_type.fromisoformat(requested_date) + timedelta(days=2)).isoformat()

    hourly_data = await get_hourly_forecast_range(
        latitude=latitude,
        longitude=longitude,
        start_date=requested_date,
        end_date=end_date,
    )
    if not hourly_data:
        return []

    candidates: list[tuple[float, SuggestedWindow]] = []

    for entry in hourly_data:
        # Skip the originally requested slot
        if entry["date"] == requested_date and entry["hour"] == requested_hour:
            continue
        # Restrict to reasonable service hours
        if not (7 <= entry["hour"] <= 19):
            continue

        w = entry["weather"]
        score, _ = _score_weather(w, service_type)

        if score < current_score:
            candidates.append((
                score,
                SuggestedWindow(
                    date=entry["date"],
                    time=f"{str(entry['hour']).zfill(2)}:00",
                    condition=w.condition,
                    temperature_c=w.temperature_c,
                    precipitation_probability=w.precipitation_probability,
                    risk_level=_get_risk_level(score),
                ),
            ))

    # Sort by score (safest first), deduplicate by date
    candidates.sort(key=lambda x: x[0])
    seen_dates: set[str] = set()
    windows: list[SuggestedWindow] = []
    for score, window in candidates:
        if window.date not in seen_dates:
            windows.append(window)
            seen_dates.add(window.date)
        if len(windows) >= max_windows:
            break

    return windows


# ── Public API ────────────────────────────────────────────────────────────────

async def assess_weather_risk(
    weather: "WeatherInfo",
    service_type: str,
    latitude: float,
    longitude: float,
    date: str,
    time: str,
) -> WeatherRiskAdvisory:
    """
    Classify the weather risk for the given slot and service type, then find
    alternative windows when risk is not SAFE.

    Args:
        weather:      The WeatherInfo for the requested slot.
        service_type: Service category string (e.g. "Electrical", "Plumbing").
        latitude:     Service location latitude.
        longitude:    Service location longitude.
        date:         Requested date as "YYYY-MM-DD".
        time:         Requested time as "HH:MM".

    Returns:
        WeatherRiskAdvisory with risk level, reasons, recommendation and
        suggested safer windows.
    """
    score, reasons = _score_weather(weather, service_type)
    level = _get_risk_level(score)

    logger.info(
        "[WeatherRisk] service_type=%s risk=%s score=%.1f reasons=%s",
        service_type, level, score, reasons,
    )

    suggested_windows: list[SuggestedWindow] = []
    if level != "SAFE":
        requested_hour = int(time.split(":")[0])
        suggested_windows = await _find_alternative_windows(
            service_type=service_type,
            latitude=latitude,
            longitude=longitude,
            requested_date=date,
            requested_hour=requested_hour,
            current_score=score,
        )
        logger.info("[WeatherRisk] Found %d alternative window(s)", len(suggested_windows))

    return WeatherRiskAdvisory(
        risk_level=level,
        risk_score=score,
        risk_reasons=reasons if reasons else ["No significant weather concerns detected"],
        recommendation=_RECOMMENDATION[level],
        suggested_windows=suggested_windows,
    )
