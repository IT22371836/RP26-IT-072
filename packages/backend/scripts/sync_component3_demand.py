import argparse
import asyncio
import json
from datetime import date

from app.components.component3.service import Component3DemandService
from app.core.config import get_settings
from app.core.firebase_database import get_database
from app.repositories.component3 import Component3Repository


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate the Component 3 weekly forecast.")
    parser.add_argument("--date", type=date.fromisoformat, help="Compile date in YYYY-MM-DD format")
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write the forecast to Firebase daily_demand/current",
    )
    return parser.parse_args()


async def run() -> None:
    args = parse_args()
    settings = get_settings()
    payload = Component3DemandService(settings.component3_artifact_dir).generate(args.date)
    if args.write:
        await Component3Repository(get_database()).save_current_forecast(payload)
    print(
        json.dumps(
            {
                "written": args.write,
                "path": Component3Repository.PATH,
                "target_week": payload["target_week"],
                "model_version": payload["model_version"],
                "category_count": len(payload["by_category"]),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    asyncio.run(run())
