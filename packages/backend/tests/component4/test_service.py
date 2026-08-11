import asyncio
import shutil

import pytest

from app.components.component4.schemas import Component4RankRequest
from app.components.component4.service import (
    ArtifactValidationError,
    Component4RankingEngine,
    Component4RankingOrchestrator,
    UnknownProviderError,
)
from app.core.config import Settings


@pytest.fixture(scope="module")
def engine() -> Component4RankingEngine:
    settings = Settings()
    instance = Component4RankingEngine(
        settings.component4_artifact_dir,
        settings.component4_category_priors_path,
    )
    instance.load()
    return instance


def rank_request(**overrides) -> Component4RankRequest:
    values = {
        "source": "development_fixture",
        "request_id": "RTEST1",
        "user_id": "UTEST1",
        "component_version": "not-component2",
        "model_version": "not-component2",
        "provider_ids": ["P00001"],
        **overrides,
    }
    return Component4RankRequest.model_validate(values)


def test_engine_loads_versioned_phase5_snapshot(engine: Component4RankingEngine) -> None:
    status = engine.status()

    assert status["ready"] is True
    assert status["provider_score_count"] == 10_000
    assert status["versions"] == {
        "catf_version": "catf-v1",
        "weight_version": "category-weights-v1",
        "category_prior_version": "category-priors-v1",
        "absa_model_version": "absa-v1",
        "credibility_model_version": "credibility-v1",
    }
    assert status["component_version"] == "component4-phase12"
    assert status["evaluation_version"] == "ranking-evaluation-v1"
    assert status["ranking_ground_truth_validation"] == "held_out_proxy_validated_phase8"
    assert status["production_ground_truth_validation"] == (
        "pending_real_component2_and_independent_relevance_judgements"
    )


def test_phase9_readiness_is_fail_closed_until_component2_exists(
    engine: Component4RankingEngine,
) -> None:
    readiness = engine.integration_readiness()

    assert readiness["phase"] == "phase9"
    assert readiness["status"] == "awaiting_component2"
    assert readiness["component4_ready"] is True
    assert readiness["component2_connected"] is False
    assert readiness["production_ready"] is False
    assert readiness["maximum_input_candidates"] == 10
    assert readiness["maximum_output_providers"] == 5
    assert readiness["fixture_policy"] == "development_only"


def test_phase10_release_evidence_passes_without_claiming_production_ready(
    engine: Component4RankingEngine,
) -> None:
    readiness = engine.release_readiness()

    assert readiness["phase"] == "phase10"
    assert readiness["status"] == "component4_ready_awaiting_component2_uat"
    assert readiness["component4_operationally_ready"] is True
    assert readiness["component2_connected"] is False
    assert readiness["production_ready"] is False
    assert all(readiness["checks"].values())
    assert readiness["performance"]["sequential"]["p95_ms"] <= 5
    assert readiness["performance"]["concurrent"]["p95_ms"] <= 20


def test_phase11_handoff_boundary_is_ready_without_claiming_component2_connection(
    engine: Component4RankingEngine,
) -> None:
    readiness = engine.handoff_readiness()

    assert readiness["phase"] == "phase11"
    assert readiness["status"] == "contract_ready_awaiting_component2"
    assert readiness["contract_enforced"] is True
    assert readiness["identity_binding_enforced"] is True
    assert readiness["lineage_persistence_enabled"] is True
    assert readiness["fixture_blocked_in_production"] is True
    assert readiness["component2_connected"] is False
    assert readiness["production_ready"] is False


def test_phase12_final_readiness_is_honest_about_external_gates(
    engine: Component4RankingEngine,
) -> None:
    readiness = engine.final_readiness()

    assert readiness["phase"] == "phase12"
    assert readiness["status"] == "component4_release_candidate_external_gates_pending"
    assert readiness["component4_release_candidate_ready"] is True
    assert readiness["component2_connected"] is False
    assert readiness["external_api_load_test_passed"] is False
    assert readiness["production_ready"] is False
    assert all(readiness["checks"].values())
    assert len(readiness["pending_external_gates"]) == 3


def test_engine_rejects_a_tampered_artifact(
    engine: Component4RankingEngine,
    tmp_path,
) -> None:
    artifact_dir = tmp_path / "catf-v1"
    artifact_dir.mkdir()
    for name in (
        "manifest.json",
        "provider_catf_scores.csv",
        "category_aspect_weights.json",
        "catf_config.json",
    ):
        shutil.copy2(engine.artifact_dir / name, artifact_dir / name)
    priors_path = tmp_path / "category_priors.json"
    shutil.copy2(engine.category_priors_path, priors_path)
    config_path = artifact_dir / "catf_config.json"
    config_path.write_text(
        config_path.read_text(encoding="utf-8") + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ArtifactValidationError, match="byte count failed"):
        Component4RankingEngine(artifact_dir, priors_path).load()


def test_engine_rejects_tampered_phase10_release_evidence(
    engine: Component4RankingEngine,
    tmp_path,
) -> None:
    release_dir = tmp_path / "release-v1"
    release_dir.mkdir()
    for name in ("manifest.json", "release_readiness.json"):
        shutil.copy2(engine.release_report_path.parent / name, release_dir / name)
    report_path = release_dir / "release_readiness.json"
    report_path.write_text(
        report_path.read_text(encoding="utf-8") + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ArtifactValidationError, match="byte count failed"):
        Component4RankingEngine(
            engine.artifact_dir,
            engine.category_priors_path,
            release_report_path=report_path,
        ).load()


def test_ranking_is_deterministic_and_never_adds_candidates(
    engine: Component4RankingEngine,
) -> None:
    candidates = [f"P{index:05d}" for index in range(1, 11)]
    first = engine.rank(
        rank_request(
            request_id="RDETERMINISTIC1",
            provider_ids=candidates,
        ),
        [],
    )
    second = engine.rank(
        rank_request(
            request_id="RDETERMINISTIC1",
            provider_ids=list(reversed(candidates)),
        ),
        [],
    )

    assert first["run_id"] == second["run_id"]
    assert first["providers"] == second["providers"]
    assert first["output_count"] == 5
    assert {
        provider["provider_id"] for provider in first["providers"]
    }.issubset(candidates)


def test_run_identity_includes_the_upstream_handoff_versions(
    engine: Component4RankingEngine,
) -> None:
    first = engine.rank(
        rank_request(
            source="component2",
            request_id="RLINEAGE2",
            component_version="component2-v1",
            model_version="context-v1",
            provider_ids=["P00001", "P00002"],
        ),
        [],
    )
    changed_model = engine.rank(
        rank_request(
            source="component2",
            request_id="RLINEAGE2",
            component_version="component2-v1",
            model_version="context-v2",
            provider_ids=["P00001", "P00002"],
        ),
        [],
    )

    assert first["run_id"] != changed_model["run_id"]
    assert first["handoff"]["model_version"] == "context-v1"
    assert changed_model["handoff"]["model_version"] == "context-v2"


def test_fewer_than_five_candidates_returns_every_candidate(
    engine: Component4RankingEngine,
) -> None:
    result = engine.rank(
        rank_request(
            request_id="RTHREE1",
            provider_ids=["P00001", "P00002", "P00003"],
        ),
        [],
    )

    assert result["input_count"] == 3
    assert result["output_count"] == 3


def test_registered_provider_uses_category_prior_fallback(
    engine: Component4RankingEngine,
) -> None:
    firebase_uid = "GsMrbJuYYHR7d0uKEqA5OVjdKV73"
    provider = {
        "provider_id": firebase_uid,
        "provider_name": "New Plumber",
        "category": "Plumbers",
        "district": "Colombo",
        "city": "Kottawa",
        "rating": 4.7,
        "review_count": 9,
    }
    result = engine.rank(
        rank_request(
            request_id="RLIVE1",
            provider_ids=[firebase_uid],
        ),
        [provider],
    )
    ranked = result["providers"][0]

    assert ranked["provider_id"] == firebase_uid
    assert ranked["score_source"] == "category_prior"
    assert ranked["final_score"] == pytest.approx(0.470486)
    assert ranked["review_count"] == 0
    assert ranked["platform_review_count"] == 9
    assert "Ranked #1 by final CATF trust score" in ranked["ranking_reason"]
    assert "Evidence source: category_prior" in ranked["ranking_reason"]


def test_unknown_provider_is_rejected(engine: Component4RankingEngine) -> None:
    with pytest.raises(UnknownProviderError, match="PUNKNOWN1"):
        engine.rank(
            rank_request(
                request_id="RUNKNOWN1",
                provider_ids=["PUNKNOWN1"],
            ),
            [],
        )


def test_unknown_category_uses_default_weight_profile(
    engine: Component4RankingEngine,
) -> None:
    profile = engine.weight_profile("Future Service")

    assert profile["profile_source"] == "default_profile"
    assert sum(profile["weights"].values()) == pytest.approx(1.0)


class InMemoryComponent4Repository:
    def __init__(self) -> None:
        self.responses: dict[str, dict[str, object]] = {}
        self.persist_count = 0
        self.provider_documents: list[dict[str, object]] = []

    async def find_completed_response(
        self,
        run_id: str,
        _user_id: str,
    ) -> dict[str, object] | None:
        return self.responses.get(run_id)

    async def persist_completed(
        self,
        run_document: dict[str, object],
        provider_documents: list[dict[str, object]],
    ) -> None:
        self.persist_count += 1
        self.responses[str(run_document["run_id"])] = run_document["response"]  # type: ignore[assignment]
        self.provider_documents = provider_documents


def test_orchestrator_persists_and_reuses_the_completed_run(
    engine: Component4RankingEngine,
) -> None:
    async def run_test() -> None:
        repository = InMemoryComponent4Repository()
        orchestrator = Component4RankingOrchestrator(engine, repository)  # type: ignore[arg-type]
        payload = rank_request(
            request_id="RCACHE1",
            provider_ids=[f"P{index:05d}" for index in range(1, 11)],
        )

        first = await orchestrator.rank(payload, user_id="UTEST1", live_providers=[])
        second = await orchestrator.rank(payload, user_id="UTEST1", live_providers=[])

        assert first.cached is False
        assert second.cached is True
        assert first.providers == second.providers
        assert repository.persist_count == 1
        assert len(repository.provider_documents) == 5
        assert first.handoff.source == "development_fixture"
        assert first.handoff.user_id == "UTEST1"
        assert repository.provider_documents[0]["handoff"] == first.handoff.model_dump()
        assert [
            document["final_catf_score"] for document in repository.provider_documents
        ] == [provider.final_score for provider in first.providers]

    asyncio.run(run_test())


def test_force_recalculate_bypasses_the_completed_run(
    engine: Component4RankingEngine,
) -> None:
    async def run_test() -> None:
        repository = InMemoryComponent4Repository()
        orchestrator = Component4RankingOrchestrator(engine, repository)  # type: ignore[arg-type]
        payload = rank_request(
            request_id="RFORCE1",
            provider_ids=["P00001", "P00002"],
            force_recalculate=True,
        )

        first = await orchestrator.rank(payload, user_id="UTEST1", live_providers=[])
        second = await orchestrator.rank(payload, user_id="UTEST1", live_providers=[])

        assert first.cached is False
        assert second.cached is False
        assert first.run_id == second.run_id
        assert repository.persist_count == 2

    asyncio.run(run_test())
