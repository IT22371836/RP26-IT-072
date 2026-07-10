from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.user import UserInDB


class UserRepository:
    """Async repository wrapping the `users` MongoDB collection."""

    COLLECTION = "users"

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self._col = db[self.COLLECTION]

    async def find_by_email(self, email: str) -> UserInDB | None:
        doc = await self._col.find_one({"email": email.lower()})
        if doc is None:
            return None
        return UserInDB.from_doc(doc)

    async def create_user(self, user: UserInDB) -> str:
        """Insert a new user document and return the inserted _id as a string."""
        result = await self._col.insert_one(user.to_doc())
        return str(result.inserted_id)

    async def email_exists(self, email: str) -> bool:
        count = await self._col.count_documents({"email": email.lower()}, limit=1)
        return count > 0

    async def ensure_indexes(self) -> None:
        """Create indexes; safe to call multiple times (idempotent)."""
        await self._col.create_index("email", unique=True)
        await self._col.create_index("role")
