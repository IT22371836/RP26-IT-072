from fastapi import APIRouter

from app.api.v1.routes.auth import router as auth_router
from app.api.v1.routes.maintenance import router as maintenance_router
from app.api.v1.routes.service_requests import router as service_requests_router

router = APIRouter()
router.include_router(auth_router)
router.include_router(maintenance_router, prefix="/maintenance", tags=["maintenance"])
router.include_router(service_requests_router, prefix="/service-requests", tags=["service-requests"])
