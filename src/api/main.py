import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from config import settings
from src.api.v1 import api_v1_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    from src.ingestion.worker import run_polling_loop

    task = asyncio.create_task(run_polling_loop())
    logger.info("Ingestion worker started")
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        logger.info("Ingestion worker stopped")


app = FastAPI(
    title="Solved Sports Analytics",
    description="Sports analytics and +EV betting platform",
    version="0.2.0",
    debug=settings.debug,
    lifespan=lifespan,
)

app.include_router(api_v1_router, prefix="/api")


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok", "environment": settings.environment.value}
