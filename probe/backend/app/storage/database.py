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
DB_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "probe_data"))
DB_PATH = os.path.join(DB_DIR, "probe.db")
DATABASE_URL = f"sqlite+aiosqlite:///{DB_PATH.replace(os.sep, '/')}"

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


async def _migrate_columns(conn) -> None:
    """Safely check and add any missing columns for existing SQLite tables."""
    from sqlalchemy import text

    migrations = {
        "tests": {
            "ai_summary": "JSON",
            "error_message": "TEXT",
            "started_at": "TIMESTAMP",
            "completed_at": "TIMESTAMP",
            "config": "JSON",
        },
        "actions": {
            "description": "TEXT",
            "success": "BOOLEAN DEFAULT 1",
            "error": "TEXT",
            "duration_ms": "FLOAT",
            "metadata": "JSON",
        },
        "observations": {
            "requested_url": "VARCHAR(2048) DEFAULT ''",
            "title": "VARCHAR(512) DEFAULT ''",
            "visible_text": "TEXT DEFAULT ''",
            "viewport": "JSON",
            "page_dimensions": "JSON",
            "status_code": "INTEGER",
            "duration_ms": "FLOAT",
            "error": "TEXT",
            "screenshot_path": "VARCHAR(1024)",
            "element_count": "INTEGER DEFAULT 0",
            "elements_data": "JSON",
            "console_messages": "JSON",
            "console_errors": "JSON",
            "js_exceptions": "JSON",
            "failed_requests": "JSON",
            "network_events": "JSON",
            "fingerprint": "VARCHAR(64)",
        },
        "evidence": {
            "content": "TEXT",
            "screenshot_path": "VARCHAR(1024)",
        },
        "findings": {
            "status": "VARCHAR(32) DEFAULT 'potential'",
            "confidence": "FLOAT DEFAULT 0.8",
            "description": "TEXT DEFAULT ''",
            "evidence": "JSON",
            "reproduction": "JSON",
            "recommendation": "TEXT",
            "ai_analysis": "JSON",
            "fingerprint": "VARCHAR(64)",
            "evidence_ids": "JSON",
        },
        "reproductions": {
            "status": "VARCHAR(32) DEFAULT 'not_attempted'",
            "attempts": "INTEGER DEFAULT 1",
            "successful_attempts": "INTEGER DEFAULT 0",
            "steps": "JSON",
            "fresh_evidence": "JSON",
            "error_message": "TEXT",
            "success": "BOOLEAN",
            "created_at": "TIMESTAMP",
            "completed_at": "TIMESTAMP",
        },
    }

    for table_name, columns in migrations.items():
        try:
            res = await conn.execute(text(f"PRAGMA table_info({table_name})"))
            existing_cols = {row[1] for row in res.fetchall()}
            for col_name, col_type in columns.items():
                if col_name not in existing_cols:
                    logger.info(f"migrating_database_column", table=table_name, column=col_name)
                    await conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type}"))
        except Exception as exc:
            logger.warning(f"migration_check_error", table=table_name, error=str(exc))


async def init_db() -> None:
    """Create all tables if they don't exist and run auto-migrations."""
    os.makedirs(DB_DIR, exist_ok=True)
    # Import models so SQLAlchemy knows about them
    from app.storage import db_models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _migrate_columns(conn)

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
