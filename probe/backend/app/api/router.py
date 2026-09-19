"""
API router — aggregates all endpoint routers.
"""
from fastapi import APIRouter

from app.api.health import router as health_router
from app.api.tests import router as tests_router

router = APIRouter()
router.include_router(health_router)
router.include_router(tests_router)
