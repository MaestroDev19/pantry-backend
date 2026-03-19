from fastapi import APIRouter

from pantry_backend.api.v1.routers.health import router as health_router
from pantry_backend.api.v1.routers.pantry import router as pantry_router
from pantry_backend.api.v1.routers.households import router as households_router
from pantry_backend.api.v1.routers.embedding_worker import router as worker_router


api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(pantry_router)
api_router.include_router(households_router)
api_router.include_router(worker_router)

