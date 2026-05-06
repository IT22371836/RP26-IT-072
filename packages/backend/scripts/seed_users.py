"""
Seed script — creates demo users in MongoDB so the platform works out of the box.

Usage (from the backend package root):
    python -m scripts.seed_users

Or directly:
    python scripts/seed_users.py
"""

import asyncio
import sys
import os

# Allow running from the backend package root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import MongoConnection
from app.core.security import hash_password
from app.models.user import UserInDB
from app.repositories.user_repository import UserRepository


DEMO_USERS = [
    {
        "email": "customer@platform.lk",
        "password": "Customer@123",
        "role": "customer",
        "full_name": "Demo Customer",
        "phone": "+94 71 234 5678",
    },
    {
        "email": "provider@platform.lk",
        "password": "Provider@123",
        "role": "provider",
        "full_name": "Demo Provider",
        "phone": "+94 77 987 6543",
        "business_name": "Demo Maintenance Co.",
        "service_types": ["Plumbing", "Electrical"],
        "address": "123 Colombo Road, Colombo 03",
    },
]


async def seed() -> None:
    await MongoConnection.connect()
    db = MongoConnection.get_db()
    repo = UserRepository(db)
    await repo.ensure_indexes()

    for user_data in DEMO_USERS:
        email = user_data["email"]
        if await repo.email_exists(email):
            print(f"  [skip] {email} already exists")
            continue

        user = UserInDB(
            id="",
            email=email,
            role=user_data["role"],  # type: ignore[arg-type]
            full_name=user_data["full_name"],
            password_hash=hash_password(user_data["password"]),
            phone=user_data.get("phone"),
            business_name=user_data.get("business_name"),
            service_types=user_data.get("service_types"),
            address=user_data.get("address"),
        )
        inserted_id = await repo.create_user(user)
        print(f"  [created] {email} (id={inserted_id})")

    await MongoConnection.disconnect()
    print("Seeding complete.")


if __name__ == "__main__":
    asyncio.run(seed())
