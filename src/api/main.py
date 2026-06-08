import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
    version="0.3.0",
    debug=settings.debug,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_v1_router, prefix="/api")


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok", "environment": settings.environment.value}
