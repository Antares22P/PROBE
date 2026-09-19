"""
SQLAlchemy ORM models for PROBE.

Tables: tests, actions, observations, evidence, findings, reproductions.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.storage.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


class TestModel(Base):
    """Persisted test session."""

    __tablename__ = "tests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    platform: Mapped[str] = mapped_column(String(16), default="web")
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    actions: Mapped[list[ActionModel]] = relationship(
        "ActionModel", back_populates="test", cascade="all, delete-orphan"
    )
    observations: Mapped[list[ObservationModel]] = relationship(
        "ObservationModel", back_populates="test", cascade="all, delete-orphan"
    )
    evidence: Mapped[list[EvidenceModel]] = relationship(
        "EvidenceModel", back_populates="test", cascade="all, delete-orphan"
    )
    findings: Mapped[list[FindingModel]] = relationship(
        "FindingModel", back_populates="test", cascade="all, delete-orphan"
    )
    reproductions: Mapped[list[ReproductionModel]] = relationship(
        "ReproductionModel", back_populates="test", cascade="all, delete-orphan"
    )


class ActionModel(Base):
    """A single action taken during a test."""

    __tablename__ = "actions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    test_id: Mapped[str] = mapped_column(ForeignKey("tests.id"), nullable=False)
    action_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict)

    test: Mapped[TestModel] = relationship("TestModel", back_populates="actions")


class ObservationModel(Base):
    """A captured application state snapshot."""

    __tablename__ = "observations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    test_id: Mapped[str] = mapped_column(ForeignKey("tests.id"), nullable=False)
    url: Mapped[str] = mapped_column(String(2048), default="")
    title: Mapped[str] = mapped_column(String(512), default="")
    element_count: Mapped[int] = mapped_column(Integer, default=0)
    console_errors: Mapped[list] = mapped_column(JSON, default=list)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    test: Mapped[TestModel] = relationship("TestModel", back_populates="observations")


class EvidenceModel(Base):
    """Captured evidence (screenshot, log, network event)."""

    __tablename__ = "evidence"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    test_id: Mapped[str] = mapped_column(ForeignKey("tests.id"), nullable=False)
    evidence_type: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    screenshot_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    test: Mapped[TestModel] = relationship("TestModel", back_populates="evidence")


class FindingModel(Base):
    """A detected issue during a test."""

    __tablename__ = "findings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    test_id: Mapped[str] = mapped_column(ForeignKey("tests.id"), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), default="info")
    category: Mapped[str] = mapped_column(String(64), default="general")
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    evidence_ids: Mapped[list] = mapped_column(JSON, default=list)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    test: Mapped[TestModel] = relationship("TestModel", back_populates="findings")


class ReproductionModel(Base):
    """A reproduction attempt for a finding."""

    __tablename__ = "reproductions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    test_id: Mapped[str] = mapped_column(ForeignKey("tests.id"), nullable=False)
    finding_id: Mapped[str] = mapped_column(String(36), nullable=False)
    success: Mapped[bool | None] = mapped_column(nullable=True)
    steps: Mapped[list] = mapped_column(JSON, default=list)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    test: Mapped[TestModel] = relationship("TestModel", back_populates="reproductions")
