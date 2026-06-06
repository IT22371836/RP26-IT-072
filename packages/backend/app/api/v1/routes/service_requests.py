import logging

from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.database import get_database
from app.repositories.service_request_repository import ServiceRequestRepository
from app.schemas.service_request import (
    MatchedProviderSchema,
    ServiceRequestCreate,
    ServiceRequestResponse,
    WeatherInfoSchema,
)
from app.services.service_request_service import ServiceRequestService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/", response_model=ServiceRequestResponse, status_code=201)
async def create_service_request(
    payload: ServiceRequestCreate,
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> ServiceRequestResponse:
    logger.info(
        "[ServiceRequest] Incoming request | service_type=%s service_issue=%s "
        "env=%s date=%s time=%s lat=%s lon=%s",
        payload.service_type,
        payload.service_issue,
        payload.service_env,
        payload.date,
        payload.time,
        payload.location.latitude,
        payload.location.longitude,
    )

    repo = ServiceRequestRepository(db)
    service = ServiceRequestService(repo)
    result, weather, matched_providers = await service.create_request(payload)

    weather_schema: WeatherInfoSchema | None = None
    if weather:
        weather_schema = WeatherInfoSchema(**weather.to_dict())
        logger.info(
            "[ServiceRequest] Weather attached | condition=%s temp=%.1f°C rain_chance=%d%%",
            weather.condition,
            weather.temperature_c,
            weather.precipitation_probability,
        )
    else:
        logger.info("[ServiceRequest] No weather data (indoor request or fetch failed)")

    provider_schemas = [MatchedProviderSchema(**p) for p in matched_providers]
    logger.info(
        "[ServiceRequest] Returning %d matched provider(s) | id=%s",
        len(provider_schemas),
        str(result["_id"]),
    )

    return ServiceRequestResponse(
        id=str(result["_id"]),
        message="Service request submitted successfully",
        weather=weather_schema,
        matched_providers=provider_schemas,
    )
