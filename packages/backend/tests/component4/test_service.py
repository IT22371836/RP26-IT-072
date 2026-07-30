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
    assert status["component_version"] == "component4-phase8"
    assert status["evaluation_version"] == "ranking-evaluation-v1"
    assert status["ranking_ground_truth_validation"] == "held_out_proxy_validated_phase8"
    assert status["production_ground_truth_validation"] == (
        "pending_real_component2_and_independent_relevance_judgements"
    )


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


def test_ranking_is_deterministic_and_never_adds_candidates(
    engine: Component4RankingEngine,
) -> None:
    candidates = [f"P{index:05d}" for index in range(1, 11)]
    first = engine.rank(
        Component4RankRequest(
            request_id="RDETERMINISTIC1",
            provider_ids=candidates,
        ),
        [],
    )
    second = engine.rank(
        Component4RankRequest(
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


def test_fewer_than_five_candidates_returns_every_candidate(
    engine: Component4RankingEngine,
) -> None:
    result = engine.rank(
        Component4RankRequest(
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
    provider = {
        "provider_id": "PNEW123",
        "provider_name": "New Plumber",
        "category": "Plumbers",
        "district": "Colombo",
        "city": "Kottawa",
        "rating": 4.7,
        "review_count": 9,
    }
    result = engine.rank(
        Component4RankRequest(
            request_id="RLIVE1",
            provider_ids=["PNEW123"],
        ),
        [provider],
    )
    ranked = result["providers"][0]

    assert ranked["provider_id"] == "PNEW123"
    assert ranked["score_source"] == "category_prior"
    assert ranked["final_score"] == pytest.approx(0.470486)
    assert ranked["review_count"] == 0
    assert ranked["platform_review_count"] == 9


def test_unknown_provider_is_rejected(engine: Component4RankingEngine) -> None:
    with pytest.raises(UnknownProviderError, match="PUNKNOWN1"):
        engine.rank(
            Component4RankRequest(
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
        payload = Component4RankRequest(
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
        payload = Component4RankRequest(
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
