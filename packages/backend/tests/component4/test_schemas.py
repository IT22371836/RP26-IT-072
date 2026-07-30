import pytest
from pydantic import ValidationError

from app.components.component4.schemas import Component4RankRequest


def handoff_fields() -> dict[str, str]:
    return {
        "source": "development_fixture",
        "user_id": "UTEST1",
        "component_version": "not-component2",
        "model_version": "not-component2",
    }


def test_rank_request_normalizes_provider_ids() -> None:
    request = Component4RankRequest(
        **handoff_fields(),
        request_id="RABC123",
        provider_ids=[" p00001 ", "P00002"],
    )

    assert request.provider_ids == ["P00001", "P00002"]
    assert request.top_k == 5
    assert request.force_recalculate is False


def test_rank_request_rejects_duplicate_provider_ids_after_normalization() -> None:
    with pytest.raises(ValidationError, match="provider_ids must be unique"):
        Component4RankRequest(
            **handoff_fields(),
            request_id="RABC123",
            provider_ids=["P00001", "p00001"],
        )


@pytest.mark.parametrize(
    ("provider_ids", "top_k"),
    [
        ([], 5),
        ([f"P{index:05d}" for index in range(11)], 5),
        (["NOT-A-PROVIDER"], 5),
        (["P00001"], 0),
        (["P00001"], 6),
    ],
)
def test_rank_request_rejects_contract_violations(
    provider_ids: list[str],
    top_k: int,
) -> None:
    with pytest.raises(ValidationError):
        Component4RankRequest(
            **handoff_fields(),
            request_id="RABC123",
            provider_ids=provider_ids,
            top_k=top_k,
        )


def test_real_component2_handoff_rejects_placeholder_versions() -> None:
    with pytest.raises(ValidationError, match="real version identifiers"):
        Component4RankRequest(
            source="component2",
            request_id="RABC123",
            user_id="UTEST1",
            component_version="not-component2",
            model_version="component2-model-v1",
            provider_ids=["P00001"],
        )
