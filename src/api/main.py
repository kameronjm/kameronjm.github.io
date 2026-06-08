from fastapi import FastAPI

from config import settings
from src.api.v1 import api_v1_router

app = FastAPI(
    title="Solved Sports Analytics",
    description="Sports analytics and +EV betting platform",
    version="0.1.0",
    debug=settings.debug,
)

app.include_router(api_v1_router, prefix="/api")


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok", "environment": settings.environment.value}
