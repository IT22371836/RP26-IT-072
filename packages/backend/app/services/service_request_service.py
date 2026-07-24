import logging

from app.repositories.service_request_repository import ServiceRequestRepository
from app.schemas.service_request import ServiceRequestCreate
from app.services.provider_matching_service import find_matching_providers
from app.services.weather_risk_service import WeatherRiskAdvisory, assess_weather_risk
from app.services.weather_service import WeatherInfo, get_weather_for_service

logger = logging.getLogger(__name__)


class ServiceRequestService:
    def __init__(self, repository: ServiceRequestRepository) -> None:
        self.repository = repository

    async def create_request(
        self, payload: ServiceRequestCreate
    ) -> tuple[dict, WeatherInfo | None, list[dict], WeatherRiskAdvisory | None]:
        data = payload.model_dump()
        weather: WeatherInfo | None = None
        weather_risk: WeatherRiskAdvisory | None = None

        # Fetch weather if the service is outdoors
        if "Outdoor" in payload.service_env:
            logger.info(
                "[ServiceRequestService] Outdoor service detected — fetching weather for "
                "lat=%s lon=%s date=%s time=%s",
                payload.location.latitude,
                payload.location.longitude,
                payload.date,
                payload.time,
            )
            # used these data to get weather details for the service request
            weather = await get_weather_for_service(
                latitude=payload.location.latitude,
                longitude=payload.location.longitude,
                date=payload.date,
                time=payload.time,
            )
            if weather:
                logger.info(
                    "[ServiceRequestService] Weather fetched successfully | %s",
                    weather.to_dict(),
                )
                data["weather"] = weather.to_dict()

                # Assess weather risk for the fetched conditions
                weather_risk = await assess_weather_risk(
                    weather=weather,
                    service_type=payload.service_type,
                    latitude=payload.location.latitude,
                    longitude=payload.location.longitude,
                    date=payload.date,
                    time=payload.time,
                )
                data["weather_risk"] = weather_risk.to_dict()
                logger.info(
                    "[ServiceRequestService] Weather risk assessed | level=%s score=%.1f",
                    weather_risk.risk_level,
                    weather_risk.risk_score,
                )
            else:
                logger.warning(
                    "[ServiceRequestService] Weather fetch returned no data for "
                    "lat=%s lon=%s date=%s time=%s",
                    payload.location.latitude,
                    payload.location.longitude,
                    payload.date,
                    payload.time,
                )
        else:
            logger.info("[ServiceRequestService] Indoor-only request — skipping weather fetch")

        # Match available providers
        matched_providers = find_matching_providers(
            service_type=payload.service_type,
            date=payload.date,
            time=payload.time,
            user_lat=payload.location.latitude,
            user_lon=payload.location.longitude,
        )
        data["matched_providers"] = matched_providers

        logger.info("[ServiceRequestService] Persisting service request to MongoDB")
        result = await self.repository.create(data)
        logger.info("[ServiceRequestService] Document inserted | _id=%s", result["_id"])
        return result, weather, matched_providers, weather_risk

    async def get_all_requests(self) -> list[dict]:
        return await self.repository.find_all()
