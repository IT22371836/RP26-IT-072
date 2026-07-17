from fastapi import APIRouter

from app.api.admin import router as admin_router
from app.api.auth import router as auth_router
from app.api.customers import router as customers_router
from app.api.health import router as health_router
from app.api.interactions import router as interactions_router
from app.api.providers import router as providers_router
from app.api.service_requests import router as service_requests_router
from app.components.component1.router import router as component1_router

api_router = APIRouter()
api_router.include_router(admin_router)
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(customers_router)
api_router.include_router(interactions_router)
api_router.include_router(providers_router)
api_router.include_router(service_requests_router)
api_router.include_router(component1_router)
