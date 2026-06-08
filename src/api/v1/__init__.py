from fastapi import APIRouter

from src.api.v1.routes import router as v1_routes

api_v1_router = APIRouter(prefix="/v1")
api_v1_router.include_router(v1_routes)

__all__ = ["api_v1_router"]
