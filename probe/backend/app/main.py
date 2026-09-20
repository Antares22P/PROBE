"""
PROBE Backend — FastAPI application entrypoint.
"""
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import router
from app.storage.database import init_db
from app.utils.errors import ProbeError
from app.utils.logging import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown."""
    logger.info("probe_starting", component="main")
    await init_db()
    logger.info("database_initialized", component="main")
    yield
    logger.info("probe_stopping", component="main")


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


@app.exception_handler(ProbeError)
async def probe_error_handler(request: Request, exc: ProbeError):
    logger.error("probe_error", code=exc.code.value, message=exc.message, path=str(request.url))
    return JSONResponse(
        status_code=400 if exc.code.value == "VALIDATION_ERROR" else 500,
        content=exc.to_response(),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error("unhandled_server_error", error=str(exc), path=str(request.url))
    return JSONResponse(
        status_code=500,
        content={"error": "INTERNAL_SERVER_ERROR", "message": str(exc)},
    )


app.include_router(router, prefix="/api")
