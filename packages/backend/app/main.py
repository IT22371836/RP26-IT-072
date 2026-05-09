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

# Normalize CORS origins from settings; allow all when none are configured (development)
cors_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
if not cors_origins:
    cors_origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(api_v1_router, prefix=settings.api_v1_prefix)
