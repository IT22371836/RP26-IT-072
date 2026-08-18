from datetime import UTC, datetime

from app.pipeline.schemas import PipelineRunResponse, PipelineStatus
from app.repositories.pipeline import pipeline_execution_event

NOW = datetime(2026, 8, 9, 12, tzinfo=UTC)


def test_component_events_expose_safe_model_versions_counts_and_runtime() -> None:
    component1 = pipeline_execution_event(
        PipelineStatus.COMPONENT1_COMPLETED,
        NOW,
        {
            "component1": {
                "engine": "hybrid_tfidf_semantic_cf",
                "component_version": "1.0.0",
                "model_version": "20260713182440",
                "artifact_provider_count": 10_000,
                "processing_time_ms": 123.4,
                "providers": [{"provider_id": f"P{index:05d}"} for index in range(20)],
            }
        },
    )
    component2 = pipeline_execution_event(
        PipelineStatus.COMPONENT2_COMPLETED,
        NOW,
        {
            "component2": {
                "engine": "deterministic_distance_hours_weather_filter",
                "component_version": "firebase-filter-v1",
                "model_version": "distance-hours-weather-v1",
                "processing_time_ms": 45.6,
                "all_evaluated_providers": [
                    {"provider_id": f"P{index:05d}"} for index in range(20)
                ],
                "output_results": {
                    "provider_ids": [f"P{index:05d}" for index in range(7)],
                    "weather_risk": "LOW",
                },
            }
        },
    )
    component4 = pipeline_execution_event(
        PipelineStatus.COMPLETED,
        NOW,
        {
            "component4": {
                "engine": "catf_precomputed_absa_credibility_ranking",
                "component_version": "4.0.0",
                "versions": {"absa_model_version": "absa-v1"},
                "input_count": 7,
                "output_count": 5,
                "pipeline_processing_time_ms": 12.3,
                "handoff": {"source": "component2"},
            }
        },
    )

    assert component1["stage"] == "component1"
    assert component1["details"]["input_provider_count"] == 10_000
    assert component1["details"]["output_provider_count"] == 20
    assert component2["details"]["output_provider_count"] == 7
    assert component2["details"]["rejected_provider_count"] == 13
    assert component2["details"]["weather_risk"] == "LOW"
    assert component4["stage"] == "component4"
    assert component4["details"]["source"] == "component2"
    assert component4["details"]["output_provider_count"] == 5
    assert component4["details"]["outside_cutoff_provider_count"] == 2


def test_older_pipeline_documents_remain_response_compatible() -> None:
    response = PipelineRunResponse.model_validate(
        {
            "run_id": "PIPE1",
            "request_id": "R1",
            "user_id": "U1",
            "status": "created",
            "request": {},
            "created_at": NOW,
            "updated_at": NOW,
        }
    )

    assert response.execution_log == []
    assert response.stage_timestamps == {}
