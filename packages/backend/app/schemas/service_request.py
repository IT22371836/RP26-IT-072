from pydantic import BaseModel


class LocationPayload(BaseModel):
    longitude: float
    latitude: float


class ServiceRequestCreate(BaseModel):
    service_type: str
    service_issue: str
    location: LocationPayload
    date: str
    time: str
    service_env: list[str]


class WeatherInfoSchema(BaseModel):
    temperature_c: float
    wind_speed_kmh: float
    precipitation_mm: float
    precipitation_probability_pct: int
    condition: str
    weather_code: int


class WorkLocationSchema(BaseModel):
    latitude: float
    longitude: float


class MatchedProviderSchema(BaseModel):
    provider_id: str
    first_name: str
    last_name: str
    service_type: str
    work_location: WorkLocationSchema
    home_address: str
    available_hours: str
    working_days: str
    distance_km: float


class ServiceRequestResponse(BaseModel):
    id: str
    message: str
    weather: WeatherInfoSchema | None = None
    matched_providers: list[MatchedProviderSchema] = []
