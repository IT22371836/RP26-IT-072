from fastapi import APIRouter

from app.api.v1.routes.auth import router as auth_router
from app.api.v1.routes.maintenance import router as maintenance_router
from app.components.component1_hybrid_recommendation_engine.router import (
	router as component1_router,
)
from app.components.component4_bilstm_crf.router import router as component4_router

router = APIRouter()
router.include_router(auth_router)
router.include_router(maintenance_router, prefix="/maintenance", tags=["maintenance"])
router.include_router(component1_router)
router.include_router(component4_router)
