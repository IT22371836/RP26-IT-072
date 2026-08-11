from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

from app.components.component4.provider_trust import (
    DEFAULT_CREDIBILITY,
    DEFAULT_PROVIDER_MAP,
    DEFAULT_RAW_REVIEWS,
)
from app.core.config import get_settings
from app.integrations.firebase_component2 import FirebaseRtdbClient

SEED_VERSION = "component4-research-reviews-v1"
IMPORT_PATH = f"research_review_imports/{SEED_VERSION}"
BATCH_PATH_COUNT = 250


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def research_customer_id(source_user_id: str) -> str:
    normalized = source_user_id.strip().upper()
    if not normalized.startswith("U") or not normalized[1:].isdigit():
        raise ValueError(f"Unsupported research user ID: {source_user_id}")
    return f"RC{normalized}"


def safe_firebase_key(value: str, label: str) -> str:
    normalized = value.strip()
    if not normalized or any(character in normalized for character in ".#$[]/"):
        raise ValueError(f"Invalid Firebase {label}: {value}")
    return normalized


def load_seed_data(
    reviews_path: Path = DEFAULT_RAW_REVIEWS,
    provider_map_path: Path = DEFAULT_PROVIDER_MAP,
    credibility_path: Path = DEFAULT_CREDIBILITY,
) -> tuple[dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]], dict[str, Any]]:
    with provider_map_path.open(encoding="utf-8-sig", newline="") as handle:
        provider_map = {
            row["source_provider_id"].strip(): row["provider_id"].strip()
            for row in csv.DictReader(handle)
        }
    with credibility_path.open(encoding="utf-8-sig", newline="") as handle:
        credibility = {
            row["review_id"].strip(): {
                "is_fake_review": row["is_fake_review"].strip() == "1",
                "credibility_score": float(row["credibility_score"]),
            }
            for row in csv.DictReader(handle)
        }

    customers: dict[str, dict[str, Any]] = {}
    provider_reviews: dict[str, list[dict[str, Any]]] = defaultdict(list)
    review_ids: set[str] = set()
    with reviews_path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            review_id = safe_firebase_key(row["review_id"], "review ID")
            if review_id in review_ids:
                raise ValueError(f"Duplicate review ID: {review_id}")
            review_ids.add(review_id)
            source_provider_id = row["provider_id"].strip()
            provider_id = provider_map.get(source_provider_id)
            evidence = credibility.get(review_id)
            if provider_id is None:
                raise ValueError(f"No canonical provider mapping for {source_provider_id}")
            if evidence is None:
                raise ValueError(f"No credibility record for {review_id}")
            source_user_id = row["user_id"].strip()
            customer_id = research_customer_id(source_user_id)
            rating = int(row["rating"])
            if not 1 <= rating <= 5:
                raise ValueError(f"Invalid rating for {review_id}: {rating}")
            record = {
                "review_id": review_id,
                "booking_id": safe_firebase_key(row["booking_id"], "booking ID"),
                "research_customer_id": customer_id,
                "source_user_id": source_user_id,
                "provider_id": safe_firebase_key(provider_id, "provider ID"),
                "source_provider_id": source_provider_id,
                "service_type": row["service_type"].strip(),
                "district": row["district"].strip(),
                "rating": rating,
                "review_text": row["review_text"].strip() or None,
                "reviewed_at": row["review_date"].strip(),
                "verified_booking": row["verified_booking"].strip() == "1",
                "dataset_split": row["dataset_split"].strip(),
                "is_fake_review": evidence["is_fake_review"],
                "credibility_score": evidence["credibility_score"],
                "usable_for_ranking": not evidence["is_fake_review"],
                "source": "component4_research_csv",
                "seed_version": SEED_VERSION,
            }
            customer = customers.setdefault(
                customer_id,
                {
                    "profile": {
                        "research_customer_id": customer_id,
                        "source_user_id": source_user_id,
                        "display_name": f"Research Customer {source_user_id}",
                        "role": "research_customer",
                        "authentication": "none",
                        "researchSeed": True,
                        "seed_version": SEED_VERSION,
                    },
                    "reviews": [],
                },
            )
            customer["reviews"].append(record)
            provider_reviews[provider_id].append(record)

    def summary(records: list[dict[str, Any]]) -> dict[str, Any]:
        ratings = [int(item["rating"]) for item in records]
        credible = sum(bool(item["usable_for_ranking"]) for item in records)
        return {
            "review_count": len(records),
            "credible_review_count": credible,
            "flagged_review_count": len(records) - credible,
            "average_rating": sum(ratings) / len(ratings) if ratings else 0.0,
            "seed_version": SEED_VERSION,
        }

    for customer in customers.values():
        customer["review_summary"] = summary(customer["reviews"])
    metadata = {
        "seed_version": SEED_VERSION,
        "review_count": len(review_ids),
        "research_customer_count": len(customers),
        "provider_count": len(provider_reviews),
        "credible_review_count": sum(
            bool(item["usable_for_ranking"])
            for records in provider_reviews.values()
            for item in records
        ),
        "source_checksums": {
            # Firebase object keys cannot contain dots, so keep stable semantic
            # labels here instead of using the source CSV filenames as keys.
            "raw_reviews": sha256_file(reviews_path),
            "provider_map": sha256_file(provider_map_path),
            "credibility": sha256_file(credibility_path),
        },
        "provider_summaries": {
            provider_id: summary(records)
            for provider_id, records in provider_reviews.items()
        },
    }
    return customers, dict(provider_reviews), metadata


def iter_write_entries(
    customers: dict[str, dict[str, Any]],
    provider_reviews: dict[str, list[dict[str, Any]]],
    metadata: dict[str, Any],
) -> Iterable[tuple[str, Any]]:
    for customer_id in sorted(customers):
        customer = customers[customer_id]
        yield f"research_customers/{customer_id}/profile", customer["profile"]
        yield (
            f"research_customers/{customer_id}/review_summary",
            customer["review_summary"],
        )
        for review in sorted(customer["reviews"], key=lambda item: item["review_id"]):
            yield (
                f"research_customers/{customer_id}/reviews/{review['review_id']}",
                review,
            )
    for provider_id in sorted(provider_reviews):
        yield (
            f"research_provider_reviews/{provider_id}/summary",
            metadata["provider_summaries"][provider_id],
        )
        for review in sorted(
            provider_reviews[provider_id], key=lambda item: item["review_id"]
        ):
            yield (
                f"research_provider_reviews/{provider_id}/reviews/{review['review_id']}",
                review,
            )


def batched(entries: Iterable[tuple[str, Any]]) -> Iterable[dict[str, Any]]:
    batch: dict[str, Any] = {}
    for path, value in entries:
        batch[path] = value
        if len(batch) >= BATCH_PATH_COUNT:
            yield batch
            batch = {}
    if batch:
        yield batch


def compatible_marker(marker: Any, metadata: dict[str, Any]) -> bool:
    return isinstance(marker, dict) and all(
        marker.get(field) == metadata.get(field)
        for field in (
            "seed_version",
            "review_count",
            "research_customer_count",
            "provider_count",
            "credible_review_count",
            "source_checksums",
        )
    )


async def run(args: argparse.Namespace) -> dict[str, Any]:
    customers, provider_reviews, metadata = await asyncio.to_thread(load_seed_data)
    firebase = FirebaseRtdbClient(get_settings())
    provider_keys, customer_keys, provider_review_keys, marker = await asyncio.gather(
        asyncio.to_thread(firebase._reference("providers").get, shallow=True),
        asyncio.to_thread(firebase._reference("research_customers").get, shallow=True),
        asyncio.to_thread(
            firebase._reference("research_provider_reviews").get, shallow=True
        ),
        asyncio.to_thread(firebase._reference(IMPORT_PATH).get),
    )
    provider_key_set = set(provider_keys or {})
    missing_providers = sorted(set(provider_reviews) - provider_key_set)
    existing_customer_count = len(customer_keys or {})
    existing_provider_index_count = len(provider_review_keys or {})
    marker_matches = compatible_marker(marker, metadata)
    conflicts: list[str] = []
    if missing_providers:
        conflicts.extend(f"missing-provider:{item}" for item in missing_providers)
    if (existing_customer_count or existing_provider_index_count) and not marker_matches:
        conflicts.append("existing-research-review-data-without-compatible-marker")

    written_batches = 0
    if args.apply and not conflicts:
        started_at = datetime.now(UTC).isoformat()
        await asyncio.to_thread(
            firebase._reference(IMPORT_PATH).set,
            {
                **{key: value for key, value in metadata.items() if key != "provider_summaries"},
                "status": "in_progress",
                "started_at": started_at,
            },
        )
        for update in batched(iter_write_entries(customers, provider_reviews, metadata)):
            await asyncio.to_thread(firebase._reference("/").update, update)
            written_batches += 1
        await asyncio.to_thread(
            firebase._reference(IMPORT_PATH).update,
            {
                "status": "completed",
                "completed_at": datetime.now(UTC).isoformat(),
                "written_batches": written_batches,
            },
        )

    verified_customers = 0
    verified_providers = 0
    verified_customer_reviews = 0
    verified_reviews = 0
    if (args.apply and not conflicts) or args.verify_only:
        stored_customers, stored_provider_reviews, stored_marker = await asyncio.gather(
            asyncio.to_thread(firebase._reference("research_customers").get),
            asyncio.to_thread(firebase._reference("research_provider_reviews").get),
            asyncio.to_thread(firebase._reference(IMPORT_PATH).get),
        )
        stored_customers = stored_customers if isinstance(stored_customers, dict) else {}
        stored_provider_reviews = (
            stored_provider_reviews if isinstance(stored_provider_reviews, dict) else {}
        )
        verified_customers = len(stored_customers)
        verified_providers = len(stored_provider_reviews)
        verified_customer_reviews = sum(
            len(value.get("reviews", {}))
            for value in stored_customers.values()
            if isinstance(value, dict) and isinstance(value.get("reviews"), dict)
        )
        verified_reviews = sum(
            len(value.get("reviews", {}))
            for value in stored_provider_reviews.values()
            if isinstance(value, dict) and isinstance(value.get("reviews"), dict)
        )
        if verified_customers != metadata["research_customer_count"]:
            conflicts.append("research-customer-count-mismatch")
        if verified_providers != metadata["provider_count"]:
            conflicts.append("provider-index-count-mismatch")
        if verified_customer_reviews != metadata["review_count"]:
            conflicts.append("customer-review-count-mismatch")
        if verified_reviews != metadata["review_count"]:
            conflicts.append("provider-review-count-mismatch")
        customer_keys_match = set(stored_customers) == set(customers) and all(
            set(
                stored_customers[customer_id].get("reviews", {})
                if isinstance(stored_customers[customer_id], dict)
                else {}
            )
            == {review["review_id"] for review in customer["reviews"]}
            for customer_id, customer in customers.items()
        )
        if not customer_keys_match:
            conflicts.append("customer-review-key-mismatch")
        provider_keys_match = set(stored_provider_reviews) == set(
            provider_reviews
        ) and all(
            set(
                stored_provider_reviews[provider_id].get("reviews", {})
                if isinstance(stored_provider_reviews[provider_id], dict)
                else {}
            )
            == {review["review_id"] for review in reviews}
            for provider_id, reviews in provider_reviews.items()
        )
        if not provider_keys_match:
            conflicts.append("provider-review-key-mismatch")
        if not compatible_marker(stored_marker, metadata) or stored_marker.get(
            "status"
        ) != "completed":
            conflicts.append("import-marker-mismatch")

    return {
        "mode": "apply" if args.apply else "verify-only" if args.verify_only else "dry-run",
        "seed_version": SEED_VERSION,
        "review_count": metadata["review_count"],
        "credible_review_count": metadata["credible_review_count"],
        "flagged_review_count": metadata["review_count"]
        - metadata["credible_review_count"],
        "research_customer_count": metadata["research_customer_count"],
        "provider_count": metadata["provider_count"],
        "missing_provider_count": len(missing_providers),
        "existing_customer_count": existing_customer_count,
        "existing_provider_index_count": existing_provider_index_count,
        "compatible_existing_import": marker_matches,
        "written_batches": written_batches,
        "verified_customer_count": verified_customers,
        "verified_customer_review_count": verified_customer_reviews,
        "verified_provider_count": verified_providers,
        "verified_provider_review_count": verified_reviews,
        "conflict_count": len(conflicts),
        "conflicts": conflicts[:100],
        "customer_path": "research_customers/{generated_id}/reviews/{review_id}",
        "provider_path": "research_provider_reviews/{provider_id}/reviews/{review_id}",
        "firebase_auth_accounts_created": 0,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import Component 4 research reviews into isolated Firebase indexes"
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--verify-only", action="store_true")
    parser.add_argument("--report", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = asyncio.run(run(args))
    rendered = json.dumps(report, indent=2)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    if report["conflict_count"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
