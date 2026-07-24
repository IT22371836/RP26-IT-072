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


class SuggestedWindowSchema(BaseModel):
    date: str
    time: str
    condition: str
    temperature_c: float
    precipitation_probability: int
    risk_level: str


class WeatherRiskSchema(BaseModel):
    risk_level: str
    risk_score: float
    risk_reasons: list[str]
    recommendation: str
    suggested_windows: list[SuggestedWindowSchema] = []


class ServiceRequestResponse(BaseModel):
    id: str
    message: str
    weather: WeatherInfoSchema | None = None
    weather_risk: WeatherRiskSchema | None = None
    matched_providers: list[MatchedProviderSchema] = []
