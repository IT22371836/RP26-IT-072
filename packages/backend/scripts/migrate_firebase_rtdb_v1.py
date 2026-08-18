import argparse
import asyncio
import json
from pathlib import Path

from app.core.config import get_settings
from app.core.database import MongoDatabase
from app.migrations.firebase_rtdb import (
    apply_snapshots,
    load_firebase_export,
    new_report,
    report_has_failures,
    verify_snapshots,
    write_report,
)
from app.repositories.legacy_firebase import LegacyFirebaseRepository
from app.repositories.users import UserRepository


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Create or verify immutable MongoDB snapshots from a Firebase RTDB JSON export."
        )
    )
    parser.add_argument("--input", type=Path, required=True, help="Firebase RTDB JSON export")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Inventory input without MongoDB")
    mode.add_argument("--apply", action="store_true", help="Insert immutable snapshots")
    mode.add_argument("--verify-only", action="store_true", help="Compare snapshots with input")
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume an apply operation; apply is always idempotent",
    )
    parser.add_argument("--report", type=Path, help="Optional JSON report output path")
    args = parser.parse_args()
    if args.resume and not args.apply:
        parser.error("--resume can only be used with --apply")
    return args


async def run_database_mode(args: argparse.Namespace, data: dict) -> dict:
    await MongoDatabase.connect(get_settings())
    try:
        database = MongoDatabase.get_database()
        repository = LegacyFirebaseRepository(database)
        if args.apply:
            return await apply_snapshots(repository, data, UserRepository(database))
        return await verify_snapshots(repository, data)
    finally:
        await MongoDatabase.disconnect()


def main() -> int:
    args = parse_args()
    data = load_firebase_export(args.input.resolve())
    if args.dry_run:
        report = new_report("dry-run", data)
    else:
        report = asyncio.run(run_database_mode(args, data))

    if args.report:
        write_report(args.report.resolve(), report)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 1 if report_has_failures(report) else 0


if __name__ == "__main__":
    raise SystemExit(main())
