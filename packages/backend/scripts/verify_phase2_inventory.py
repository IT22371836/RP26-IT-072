import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from app.migrations.firebase_rtdb import load_firebase_export
from app.migrations.phase2_inventory import verify_phase2_inventory


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify lossless Phase 2 Firebase attribute preservation."
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    data = load_firebase_export(args.input.resolve())
    report = verify_phase2_inventory(data)
    report["generated_at"] = datetime.now(UTC).isoformat()
    report["source_file"] = args.input.name
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report["summary"], sort_keys=True))
    return 0 if report["summary"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
