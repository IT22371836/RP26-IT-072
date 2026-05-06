"""
Seed demo Weda requests.

Usage (from backend package root):
    python -m scripts.seed_Weda
"""

import asyncio
import sys
import os
from datetime import datetime, timedelta

# Allow running from the backend package root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import MongoConnection


DEMO_REQUESTS = [
    {
        "customer_id": "customer@platform.lk",
        "provider_id": "provider@platform.lk",
        "asset_type": "AC",
        "description": "AC not cooling, needs gas refill",
        "status": "open",
        "priority": "high",
        "eta": datetime.utcnow() + timedelta(hours=4),
        "created_at": datetime.utcnow(),
        "updated_at": None,
    },
    {
        "customer_id": "customer@platform.lk",
        "provider_id": None,
        "asset_type": "Plumbing",
        "description": "Leaky faucet in kitchen",
        "status": "assigned",
        "priority": "normal",
        "eta": datetime.utcnow() + timedelta(days=1),
        "created_at": datetime.utcnow() - timedelta(days=1),
        "updated_at": None,
    },
]


async def seed() -> None:
    await MongoConnection.connect()
    db = MongoConnection.get_db()
    col = db["Weda_requests"]

    # create indexes
    await col.create_index("customer_id")
    await col.create_index("provider_id")
    await col.create_index("status")

    for req in DEMO_REQUESTS:
        # avoid duplicates by simple match on description + customer
        exists = await col.count_documents({"customer_id": req["customer_id"], "description": req["description"]}, limit=1)
        if exists:
            print(f"  [skip] request exists: {req['description']}")
            continue
        result = await col.insert_one(req)
        print(f"  [created] request id={result.inserted_id}")

    await MongoConnection.disconnect()
    print("Seeding Wedacomplete.")


if __name__ == "__main__":
    asyncio.run(seed())
