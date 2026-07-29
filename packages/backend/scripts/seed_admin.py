import argparse
import asyncio
import getpass
import os

from pydantic import EmailStr, TypeAdapter, ValidationError

from app.core.config import get_settings
from app.core.database import MongoDatabase
from app.core.security import hash_password
from app.repositories.users import UserRepository
from app.schemas.common import UserRole, new_public_id, utc_now


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create or refresh a local administrator account.")
    parser.add_argument("--email", required=True)
    parser.add_argument("--full-name", default="Platform Administrator")
    return parser.parse_args()


async def seed(email: str, full_name: str, password: str) -> None:
    settings = get_settings()
    await MongoDatabase.connect(settings)
    try:
        repository = UserRepository(MongoDatabase.get_database())
        existing = await repository.find_by_email(email)
        document = {
            "email": email,
            "full_name": " ".join(full_name.split()),
            "hashed_password": hash_password(password),
            "role": UserRole.ADMIN.value,
            "is_active": True,
        }
        if existing is None:
            document.update({"user_id": new_public_id("U"), "created_at": utc_now()})
            await repository.create(document)
            action = "created"
        elif existing["role"] != UserRole.ADMIN.value:
            raise RuntimeError("That email already belongs to a non-admin account.")
        else:
            await repository.collection.update_one(
                {"user_id": existing["user_id"]}, {"$set": document}
            )
            action = "updated"
        print(f"Admin account {action}: {email}")
    finally:
        await MongoDatabase.disconnect()


def main() -> None:
    args = arguments()
    try:
        email = str(TypeAdapter(EmailStr).validate_python(args.email)).lower()
    except ValidationError as error:
        raise SystemExit("A valid --email is required.") from error
    password = os.getenv("WEDA_ADMIN_PASSWORD") or getpass.getpass("Admin password: ")
    if len(password) < 8:
        raise SystemExit("Admin password must contain at least 8 characters.")
    asyncio.run(seed(email, args.full_name, password))


if __name__ == "__main__":
    main()
