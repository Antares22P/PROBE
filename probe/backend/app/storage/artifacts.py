"""
Artifact Storage abstraction and local filesystem implementation.

Stores screenshots, DOM dumps, traces, and reports without cluttering the database.
"""
from __future__ import annotations

import os
import uuid
from abc import ABC, abstractmethod
from typing import Optional

from app.storage.database import DB_DIR
from app.utils.logging import get_logger

logger = get_logger(__name__)

DEFAULT_ARTIFACTS_DIR = os.path.join(DB_DIR, "artifacts")


class ArtifactStorage(ABC):
    """Abstract interface for storing test artifacts."""

    @abstractmethod
    async def save_screenshot(
        self, test_id: str, image_bytes: bytes, name: Optional[str] = None
    ) -> str:
        """Save screenshot bytes and return the relative or absolute path identifier."""
        ...

    @abstractmethod
    async def get_screenshot(self, path_or_key: str) -> Optional[bytes]:
        """Read screenshot bytes from storage."""
        ...

    @abstractmethod
    async def save_data(
        self, test_id: str, data: str | bytes, filename: str
    ) -> str:
        """Save text/binary artifact and return path."""
        ...

    @abstractmethod
    async def get_data(self, path_or_key: str) -> Optional[bytes]:
        """Read arbitrary artifact bytes."""
        ...


class LocalArtifactStorage(ArtifactStorage):
    """Stores test artifacts on local filesystem."""

    def __init__(self, base_dir: str = DEFAULT_ARTIFACTS_DIR) -> None:
        self.base_dir = os.path.abspath(base_dir)
        os.makedirs(self.base_dir, exist_ok=True)

    def _test_dir(self, test_id: str) -> str:
        path = os.path.join(self.base_dir, test_id)
        os.makedirs(path, exist_ok=True)
        return path

    async def save_screenshot(
        self, test_id: str, image_bytes: bytes, name: Optional[str] = None
    ) -> str:
        tdir = self._test_dir(test_id)
        filename = name or f"screenshot_{uuid.uuid4().hex[:8]}.png"
        if not filename.endswith(".png"):
            filename = f"{filename}.png"
        filepath = os.path.join(tdir, filename)
        with open(filepath, "wb") as f:
            f.write(image_bytes)
        logger.debug("screenshot_saved", path=filepath, size=len(image_bytes))
        return filepath

    async def get_screenshot(self, path_or_key: str) -> Optional[bytes]:
        if not path_or_key:
            return None
        target = path_or_key
        if not os.path.isabs(target):
            target = os.path.join(self.base_dir, target)
        if not os.path.exists(target):
            return None
        with open(target, "rb") as f:
            return f.read()

    async def save_data(
        self, test_id: str, data: str | bytes, filename: str
    ) -> str:
        tdir = self._test_dir(test_id)
        filepath = os.path.join(tdir, filename)
        mode = "wb" if isinstance(data, bytes) else "w"
        encoding = None if isinstance(data, bytes) else "utf-8"
        with open(filepath, mode, encoding=encoding) as f:
            f.write(data)
        return filepath

    async def get_data(self, path_or_key: str) -> Optional[bytes]:
        if not path_or_key:
            return None
        target = path_or_key
        if not os.path.isabs(target):
            target = os.path.join(self.base_dir, target)
        if not os.path.exists(target):
            return None
        with open(target, "rb") as f:
            return f.read()


# Singleton default storage instance
default_artifact_storage = LocalArtifactStorage()
