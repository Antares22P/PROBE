"""
SQLAlchemy database engine and session management.

Uses SQLite with aiosqlite for async support.
"""
from __future__ import annotations

import os
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.utils.logging import get_logger

logger = get_logger(__name__)

# Database location
DB_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "probe_data")
DB_PATH = os.path.join(DB_DIR, "probe.db")
DATABASE_URL = f"sqlite+aiosqlite:///{DB_PATH}"

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""
    pass


async def init_db() -> None:
    """Create all tables if they don't exist."""
    os.makedirs(DB_DIR, exist_ok=True)
    # Import models so SQLAlchemy knows about them
    from app.storage import db_models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    logger.info("db_ready", component="database", path=DB_PATH)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: yields an async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
