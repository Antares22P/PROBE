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
    ai_summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)

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
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    success: Mapped[bool] = mapped_column(default=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[float | None] = mapped_column(nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict)

    test: Mapped[TestModel] = relationship("TestModel", back_populates="actions")


class ObservationModel(Base):
    """A captured application state snapshot."""

    __tablename__ = "observations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    test_id: Mapped[str] = mapped_column(ForeignKey("tests.id"), nullable=False)
    url: Mapped[str] = mapped_column(String(2048), default="")
    requested_url: Mapped[str] = mapped_column(String(2048), default="")
    title: Mapped[str] = mapped_column(String(512), default="")
    visible_text: Mapped[str] = mapped_column(Text, default="")
    viewport: Mapped[dict] = mapped_column(JSON, default=dict)
    page_dimensions: Mapped[dict] = mapped_column(JSON, default=dict)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_ms: Mapped[float | None] = mapped_column(nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    screenshot_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    element_count: Mapped[int] = mapped_column(Integer, default=0)
    elements_data: Mapped[list] = mapped_column(JSON, default=list)
    console_messages: Mapped[list] = mapped_column(JSON, default=list)
    console_errors: Mapped[list] = mapped_column(JSON, default=list)
    js_exceptions: Mapped[list] = mapped_column(JSON, default=list)
    failed_requests: Mapped[list] = mapped_column(JSON, default=list)
    network_events: Mapped[list] = mapped_column(JSON, default=list)
    fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
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
    severity: Mapped[str] = mapped_column(String(16), default="medium")
    category: Mapped[str] = mapped_column(String(64), default="other")
    status: Mapped[str] = mapped_column(String(32), default="potential")
    confidence: Mapped[float] = mapped_column(default=0.8)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    evidence: Mapped[list] = mapped_column(JSON, default=list)
    reproduction: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    recommendation: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_analysis: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    evidence_ids: Mapped[list] = mapped_column(JSON, default=list)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    test: Mapped[TestModel] = relationship("TestModel", back_populates="findings")


class ReproductionModel(Base):
    """A reproduction attempt for a finding."""

    __tablename__ = "reproductions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    test_id: Mapped[str] = mapped_column(ForeignKey("tests.id"), nullable=False)
    finding_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), default="not_attempted")
    attempts: Mapped[int] = mapped_column(Integer, default=1)
    successful_attempts: Mapped[int] = mapped_column(Integer, default=0)
    steps: Mapped[list] = mapped_column(JSON, default=list)
    fresh_evidence: Mapped[list] = mapped_column(JSON, default=list)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    success: Mapped[bool | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    test: Mapped[TestModel] = relationship("TestModel", back_populates="reproductions")
