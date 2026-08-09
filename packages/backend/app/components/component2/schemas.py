from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class ServiceTime(BaseModel):
    start_time: str = Field(min_length=4, max_length=20)
    end_time: str = Field(min_length=4, max_length=20)

    @staticmethod
    def parse(value: str):
        for fmt in ("%I:%M %p", "%H:%M", "%I:%M%p"):
            try:
                return datetime.strptime(value.strip(), fmt).time()
            except ValueError:
                continue
        raise ValueError("time must use HH:MM or HH:MM AM/PM")

    @model_validator(mode="after")
    def validate_range(self) -> ServiceTime:
        if self.parse(self.end_time) <= self.parse(self.start_time):
            raise ValueError("end_time must be after start_time")
        return self


class Component2FilterRequest(BaseModel):
    request_id: str = Field(pattern=r"^R[A-Z0-9]+$", min_length=2, max_length=64)
    user_id: str = Field(min_length=1, max_length=128)
    location_type: Literal["indoor", "outdoor", "indoor and outdoor"]
    service_date: date
    service_time: ServiceTime
    isNewRequest: bool = True
    results: dict[str, list[str]]
    pipeline: dict = Field(default_factory=dict)

    @field_validator("service_date")
    @classmethod
    def validate_forecast_window(cls, value: date) -> date:
        today = date.today()
        if value < today or value > today + timedelta(days=6):
            raise ValueError("service_date must be within the seven-day forecast window")
        return value

    @model_validator(mode="after")
    def validate_candidates(self) -> Component2FilterRequest:
        provider_ids = self.results.get("provider_ids", [])
        if not 1 <= len(provider_ids) <= 20:
            raise ValueError("results.provider_ids must contain between 1 and 20 providers")
        if len(provider_ids) != len(set(provider_ids)):
            raise ValueError("results.provider_ids must be unique")
        if any(not item.startswith("P") for item in provider_ids):
            raise ValueError("provider IDs must be canonical IDs beginning with P")
        return self


class Component2FilterResult(BaseModel):
    output_results: dict
    all_evaluated_providers: list[dict]
    component_version: str
    model_version: str
