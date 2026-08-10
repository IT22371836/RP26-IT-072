from datetime import date, timedelta

from app.components.component2.schemas import Component2FilterRequest
from app.components.component2.service import Component2FilteringService
from app.components.component4.schemas import Component4RankRequest


FIREBASE_PROVIDER_UID = "GsMrbJuYYHR7d0uKEqA5OVjdKV73"


def request(provider_ids: list[str]) -> Component2FilterRequest:
    return Component2FilterRequest.model_validate(
        {
            "request_id": "RPIPELINE1",
            "user_id": "firebase-customer",
            "location_type": "indoor",
            "service_date": (date.today() + timedelta(days=1)).isoformat(),
            "service_time": {"start_time": "09:00", "end_time": "11:00"},
            "isNewRequest": True,
            "results": {"provider_ids": provider_ids},
            "pipeline": {"run_id": "PIPELINE1"},
        }
    )


def provider(*, open_for_work: bool) -> dict:
    return {
        "fullName": "Research Provider",
        "location": {"latitude": 6.9271, "longitude": 79.8612},
        "workingHours": {
            day: {
                "isOpen": open_for_work,
                "start": "08:00 AM",
                "end": "06:00 PM",
            }
            for day in (
                "Monday",
                "Tuesday",
                "Wednesday",
                "Thursday",
                "Friday",
                "Saturday",
                "Sunday",
            )
        },
    }


def service() -> Component2FilteringService:
    return Component2FilteringService(
        component_version="component2-v1",
        model_version="filter-v1",
        weather_fetcher=lambda *_args, **_kwargs: None,
    )


def test_component2_preserves_contract_and_returns_only_c1_subset() -> None:
    payload = request(["P00001", "P00002"])
    result = service().filter(
        payload,
        {"location": {"latitude": 6.9271, "longitude": 79.8612}},
        {"P00001": provider(open_for_work=True), "P00002": provider(open_for_work=False)},
    )
    assert set(result.output_results) == {
        "provider_ids",
        "evaluated_providers",
        "weather_risk",
        "recommendation",
        "weather_summary",
        "evaluated_at",
    }
    assert result.output_results["provider_ids"] == ["P00001"]
    assert result.output_results["weather_risk"] == "UNKNOWN"
    assert len(result.all_evaluated_providers) == 2


def test_zero_result_is_preserved_and_fallback_source_is_valid() -> None:
    payload = request(["P00001"])
    result = service().filter(
        payload,
        {"location": {"latitude": 6.9271, "longitude": 79.8612}},
        {"P00001": provider(open_for_work=False)},
    )
    assert result.output_results["provider_ids"] == []
    handoff = Component4RankRequest(
        source="component2_zero_fallback",
        request_id=payload.request_id,
        user_id="U00001",
        component_version="component2-v1",
        model_version="filter-v1",
        provider_ids=["P00001"],
    )
    assert handoff.source == "component2_zero_fallback"


def test_component2_and_component4_preserve_case_sensitive_firebase_uid() -> None:
    payload = request([FIREBASE_PROVIDER_UID])
    handoff = Component4RankRequest(
        source="component2",
        request_id=payload.request_id,
        user_id="U00001",
        component_version="component2-v1",
        model_version="filter-v1",
        provider_ids=[FIREBASE_PROVIDER_UID],
    )

    assert payload.results["provider_ids"] == [FIREBASE_PROVIDER_UID]
    assert handoff.provider_ids == [FIREBASE_PROVIDER_UID]


def test_component2_rejects_dates_outside_forecast_window() -> None:
    data = request(["P00001"]).model_dump(mode="json")
    data["service_date"] = (date.today() + timedelta(days=7)).isoformat()
    try:
        Component2FilterRequest.model_validate(data)
    except ValueError as error:
        assert "seven-day forecast window" in str(error)
    else:
        raise AssertionError("Date outside the forecast window was accepted")
