import pytest
from pydantic import ValidationError

from app.components.component1.schemas import RecommendationRequest


def test_recommendation_request_normalizes_query_and_preserves_request_id() -> None:
    request = RecommendationRequest(
        request_id="RABC123",
        query="  need   an electrician  ",
    )

    assert request.request_id == "RABC123"
    assert request.query == "need an electrician"
    assert request.top_k == 20


@pytest.mark.parametrize("query", ["   ", " a "])
def test_recommendation_request_rejects_effectively_empty_query(query: str) -> None:
    with pytest.raises(ValidationError):
        RecommendationRequest(request_id="RABC123", query=query)


def test_recommendation_request_rejects_noncanonical_request_id() -> None:
    with pytest.raises(ValidationError):
        RecommendationRequest(request_id="123", query="electrician")
