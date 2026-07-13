import csv
import json
from pathlib import Path

from app.schemas.interaction import InteractionDatasetRecord
from app.schemas.provider import ProviderDatasetRecord
from app.schemas.service_request import ServiceRequestDatasetRecord

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = REPOSITORY_ROOT / "ml" / "components" / "component1" / "data" / "raw"


def test_provider_dataset_matches_shared_contract() -> None:
    path = DATA_DIR / "SL_Provider_Dataset_10000_Research_Grade.json"
    with path.open(encoding="utf-8") as file:
        first_provider = json.load(file)[0]

    provider = ProviderDatasetRecord.model_validate(first_provider)
    assert provider.provider_id.startswith("P")


def test_request_dataset_matches_pipeline_contract() -> None:
    path = DATA_DIR / "SL_User_Request_Dataset_20000.csv"
    with path.open(encoding="utf-8", newline="") as file:
        first_request = next(csv.DictReader(file))

    request = ServiceRequestDatasetRecord.model_validate(first_request)
    assert request.request_id.startswith("R")
    assert request.user_id.startswith("U")


def test_interaction_dataset_preserves_shared_identifiers() -> None:
    path = DATA_DIR / "SL_User_Interaction_Dataset_100000.csv"
    with path.open(encoding="utf-8", newline="") as file:
        first_interaction = next(csv.DictReader(file))

    interaction = InteractionDatasetRecord.model_validate(first_interaction)
    assert interaction.interaction_id.startswith("I")
    assert interaction.user_id.startswith("U")
    assert interaction.provider_id.startswith("P")
