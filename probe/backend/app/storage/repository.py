"""
Repository — data access layer for PROBE storage.

All database operations go through this layer.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.storage.db_models import (
    ActionModel,
    EvidenceModel,
    FindingModel,
    ObservationModel,
    ReproductionModel,
    TestModel,
)
from app.utils.errors import DatabaseError
from app.utils.logging import get_logger

logger = get_logger(__name__)


class TestRepository:
    """Data access for test sessions."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(self, test: TestModel) -> TestModel:
        try:
            self._db.add(test)
            await self._db.flush()
            await self._db.refresh(test)
            logger.info("test_created", component="repository", test_id=test.id)
            return test
        except Exception as exc:
            raise DatabaseError(f"Failed to create test: {exc}") from exc

    async def get(self, test_id: str) -> Optional[TestModel]:
        try:
            result = await self._db.execute(select(TestModel).where(TestModel.id == test_id))
            return result.scalar_one_or_none()
        except Exception as exc:
            raise DatabaseError(f"Failed to get test {test_id}: {exc}") from exc

    async def list_all(self, limit: int = 100, offset: int = 0) -> list[TestModel]:
        try:
            result = await self._db.execute(
                select(TestModel)
                .order_by(TestModel.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            return list(result.scalars().all())
        except Exception as exc:
            raise DatabaseError(f"Failed to list tests: {exc}") from exc

    async def update_status(
        self,
        test_id: str,
        status: str,
        error_message: Optional[str] = None,
    ) -> Optional[TestModel]:
        try:
            test = await self.get(test_id)
            if test is None:
                return None
            test.status = status
            test.updated_at = datetime.now(timezone.utc)
            if status == "running" and test.started_at is None:
                test.started_at = datetime.now(timezone.utc)
            if status in ("completed", "failed", "cancelled"):
                test.completed_at = datetime.now(timezone.utc)
            if error_message is not None:
                test.error_message = error_message
            await self._db.flush()
            await self._db.refresh(test)
            return test
        except DatabaseError:
            raise
        except Exception as exc:
            raise DatabaseError(f"Failed to update test status: {exc}") from exc

    async def add_observation(self, obs: ObservationModel) -> ObservationModel:
        try:
            self._db.add(obs)
            await self._db.flush()
            return obs
        except Exception as exc:
            raise DatabaseError(f"Failed to add observation: {exc}") from exc

    async def add_evidence(self, ev: EvidenceModel) -> EvidenceModel:
        try:
            self._db.add(ev)
            await self._db.flush()
            return ev
        except Exception as exc:
            raise DatabaseError(f"Failed to add evidence: {exc}") from exc

    async def add_finding(self, finding: FindingModel) -> FindingModel:
        try:
            self._db.add(finding)
            await self._db.flush()
            return finding
        except Exception as exc:
            raise DatabaseError(f"Failed to add finding: {exc}") from exc
