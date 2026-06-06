import logging

from app.repositories.service_request_repository import ServiceRequestRepository
from app.schemas.service_request import ServiceRequestCreate
from app.services.provider_matching_service import find_matching_providers
from app.services.weather_service import WeatherInfo, get_weather_for_service

logger = logging.getLogger(__name__)


class ServiceRequestService:
    def __init__(self, repository: ServiceRequestRepository) -> None:
        self.repository = repository

    async def create_request(
        self, payload: ServiceRequestCreate
    ) -> tuple[dict, WeatherInfo | None, list[dict]]:
        data = payload.model_dump()
        weather: WeatherInfo | None = None

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
        return result, weather, matched_providers

    async def get_all_requests(self) -> list[dict]:
        return await self.repository.find_all()
