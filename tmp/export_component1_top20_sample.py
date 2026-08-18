import json
from pathlib import Path

from app.components.component1.schemas import RecommendationResponse
from app.components.component1.service import HybridRecommendationEngine
from app.core.config import get_settings


def main() -> None:
    settings = get_settings()
    engine = HybridRecommendationEngine(settings.component1_artifact_dir)
    engine.load()
    results = engine.recommend(
        query="Need a qualified electrician for house wiring and damaged socket repair",
        user_id="UCOMPONENT2HANDOFF",
        top_k=20,
        category="Electricians",
        district="Colombo",
        city="Kottawa",
    )
    response = RecommendationResponse(
        component_version=engine.manifest["component_version"],
        model_version=engine.manifest["model_version"],
        request_id="RCOMPONENT2HANDOFF",
        query="Need a qualified electrician for house wiring and damaged socket repair",
        user_id="UCOMPONENT2HANDOFF",
        results=results,
    )
    output = (
        Path(__file__).resolve().parents[1]
        / "docs"
        / "integration"
        / "component1-top20-output-sample.json"
    )
    output.write_text(
        json.dumps(response.model_dump(mode="json"), indent=2),
        encoding="utf-8",
    )
    print(output)


if __name__ == "__main__":
    main()
