from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.database import get_database

router = APIRouter()


@router.get("/")
async def list_maintenance_requests(db: AsyncIOMotorDatabase = Depends(get_database)) -> dict:
    total = await db["maintenance_requests"].count_documents({})
    return {"total": total, "items": []}
