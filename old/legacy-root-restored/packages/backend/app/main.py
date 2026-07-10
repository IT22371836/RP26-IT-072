from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.api.v1.router import router as api_v1_router
from app.core.config import settings
from app.core.database import MongoConnection
from app.repositories.user_repository import UserRepository


@asynccontextmanager
async def lifespan(_: FastAPI):
    await MongoConnection.connect()
    # Ensure unique email index exists
    db = MongoConnection.get_db()
    await UserRepository(db).ensure_indexes()
    yield
    await MongoConnection.disconnect()


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(api_v1_router, prefix=settings.api_v1_prefix)
