"""
Weather Service — Open-Meteo Integration
Fetches hourly weather forecast for a given location, date and time.
Open-Meteo is free, open-source and requires no API key.
Docs: https://open-meteo.com/en/docs
"""
from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

# WMO Weather Interpretation Codes → human-readable descriptions
WMO_CODES: dict[int, str] = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Foggy",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    71: "Slight snow",
    73: "Moderate snow",
    75: "Heavy snow",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}


class WeatherInfo:
    """Holds weather conditions for a specific date/time/location."""

    def __init__(
        self,
        temperature_c: float,
        wind_speed_kmh: float,
        precipitation_mm: float,
        precipitation_probability: int,
        condition: str,
        weather_code: int,
    ) -> None:
        self.temperature_c = temperature_c
        self.wind_speed_kmh = wind_speed_kmh
        self.precipitation_mm = precipitation_mm
        self.precipitation_probability = precipitation_probability
        self.condition = condition
        self.weather_code = weather_code

    def to_dict(self) -> dict:
        return {
            "temperature_c": self.temperature_c,
            "wind_speed_kmh": self.wind_speed_kmh,
            "precipitation_mm": self.precipitation_mm,
            "precipitation_probability_pct": self.precipitation_probability,
            "condition": self.condition,
            "weather_code": self.weather_code,
        }


async def get_weather_for_service(
    latitude: float,
    longitude: float,
    date: str,   # "YYYY-MM-DD"
    time: str,   # "HH:MM"
) -> WeatherInfo | None:
    """
    Calls Open-Meteo forecast API and returns hourly weather data
    for the given latitude, longitude, date and hour.
    Returns None if the API call fails or data is unavailable.
    """
    from datetime import date as date_type, timedelta
    import datetime

    target_hour = int(time.split(":")[0])  # e.g. "09:30" → 9

    # Open-Meteo free tier supports forecasts up to 16 days from today.
    requested_date = datetime.date.fromisoformat(date)
    today = datetime.date.today()
    max_forecast_date = today + timedelta(days=16)
    if requested_date < today:
        logger.warning(
            "[WeatherService] Requested date %s is in the past — skipping weather fetch",
            date,
        )
        return None
    if requested_date > max_forecast_date:
        logger.warning(
            "[WeatherService] Requested date %s is beyond the 16-day forecast window "
            "(max allowed: %s) — skipping weather fetch",
            date,
            max_forecast_date.isoformat(),
        )
        return None

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "hourly": "temperature_2m,precipitation,precipitation_probability,weathercode,windspeed_10m",
        "start_date": date,
        "end_date": date,
        "timezone": "Asia/Colombo",
    }

    try:
        logger.debug(
            "[WeatherService] Calling Open-Meteo | url=%s params=%s",
            OPEN_METEO_URL,
            params,
        )
        # open meteo API to get weather details for the service request
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(OPEN_METEO_URL, params=params)
            response.raise_for_status()
            data = response.json()
        logger.debug("[WeatherService] Open-Meteo response received | status=%s", response.status_code)
    except httpx.TimeoutException:
        logger.error("[WeatherService] Request timed out for lat=%s lon=%s", latitude, longitude)
        return None
    except httpx.HTTPStatusError as exc:
        logger.error(
            "[WeatherService] HTTP error from Open-Meteo | status=%s body=%s",
            exc.response.status_code,
            exc.response.text[:200],
        )
        return None
    except Exception as exc:
        logger.error("[WeatherService] Unexpected error: %s", exc)
        return None

    hourly = data.get("hourly", {})
    times: list[str] = hourly.get("time", [])

    # Find the index matching the requested date+hour
    target_time_str = f"{date}T{str(target_hour).zfill(2)}:00"
    logger.debug("[WeatherService] Looking for time slot: %s in %d entries", target_time_str, len(times))
    try:
        idx = times.index(target_time_str)
    except ValueError:
        logger.warning(
            "[WeatherService] Time slot '%s' not found in forecast data. "
            "Date may be beyond the 16-day forecast window.",
            target_time_str,
        )
        return None

    weather_code: int = int(hourly["weathercode"][idx])
    logger.info(
        "[WeatherService] Result | time=%s code=%d condition=%s temp=%.1f°C wind=%.1f km/h rain=%dmm chance=%d%%",
        target_time_str,
        weather_code,
        WMO_CODES.get(weather_code, "Unknown"),
        float(hourly["temperature_2m"][idx]),
        float(hourly["windspeed_10m"][idx]),
        float(hourly["precipitation"][idx]),
        int(hourly["precipitation_probability"][idx]),
    )

    return WeatherInfo(
        temperature_c=float(hourly["temperature_2m"][idx]),
        wind_speed_kmh=float(hourly["windspeed_10m"][idx]),
        precipitation_mm=float(hourly["precipitation"][idx]),
        precipitation_probability=int(hourly["precipitation_probability"][idx]),
        condition=WMO_CODES.get(weather_code, "Unknown"),
        weather_code=weather_code,
    )
