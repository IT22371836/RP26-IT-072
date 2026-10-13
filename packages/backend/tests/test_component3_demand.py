from datetime import date
from pathlib import Path

import numpy as np

from app.components.component3.service import (
    SERVICE_CATEGORIES,
    Component3DemandService,
    demand_level,
    next_week_dates,
)
from app.schemas.integration import DailyDemandRecord


class PassThroughEncoder:
    def transform(self, frame):
        return frame


class SequenceModel:
    def predict(self, frame):
        return np.arange(1, len(frame) + 1, dtype=float)


def test_demand_thresholds_match_research_contract() -> None:
    assert demand_level(10) == "LOW"
    assert demand_level(10.1) == "MEDIUM"
    assert demand_level(25) == "MEDIUM"
    assert demand_level(25.1) == "HIGH"


def test_forecast_always_targets_the_following_monday_to_sunday() -> None:
    dates = next_week_dates(date(2026, 8, 3))
    assert dates[0] == date(2026, 8, 10)
    assert dates[-1] == date(2026, 8, 16)


def test_generated_payload_preserves_daily_demand_frontend_contract() -> None:
    service = Component3DemandService(
        Path("unused-in-injected-test"),
        model=SequenceModel(),
        target_encoder=PassThroughEncoder(),
        feature_columns=["month", "weekend", "previous_day_orders"],
    )

    payload = service.generate(date(2026, 8, 5))

    assert payload["start_date"] == "2026-08-10"
    assert payload["end_date"] == "2026-08-16"
    assert payload["model_version"] == "demand-v1"
    assert len(payload["by_category"]) == len(SERVICE_CATEGORIES)
    assert len(payload["summary"]) == len(SERVICE_CATEGORIES)
    assert "A_C Services" in payload["by_category"]
    assert set(payload["by_category"]["Electricians"]) >= {
        "Monday",
        "Sunday",
        "total_weekly",
        "avg_daily",
        "demand_level",
    }


def test_shipped_artifact_bundle_generates_all_categories() -> None:
    artifact_dir = (
        Path(__file__).resolve().parents[3]
        / "ml"
        / "components"
        / "component3"
        / "artifacts"
        / "demand-v1"
    )

    payload = Component3DemandService(artifact_dir).generate(date(2026, 8, 5))

    assert payload["model_version"] == "demand-v1"
    assert len(payload["by_category"]) == 14
    assert all(item["Total Weekly Orders"] >= 7 for item in payload["summary"])
    DailyDemandRecord.model_validate(payload)
