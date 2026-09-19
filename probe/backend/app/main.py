"""
PROBE Backend — FastAPI application entrypoint.
"""
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import router
from app.storage.database import init_db
from app.utils.logging import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown."""
    logger.info("startup", component="main", event="probe_starting")
    await init_db()
    logger.info("startup", component="main", event="database_initialized")
    yield
    logger.info("shutdown", component="main", event="probe_stopping")


app = FastAPI(
    title="PROBE API",
    description="Autonomous Web Application Testing Platform",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")
