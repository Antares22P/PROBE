"""
PROBE error types.

Distinguishes: VALIDATION_ERROR, DRIVER_ERROR, DATABASE_ERROR, API_ERROR, INTERNAL_ERROR.
Raw stack traces are never exposed to the frontend.
"""
from enum import Enum
from typing import Any, Optional


class ErrorCode(str, Enum):
    VALIDATION_ERROR = "VALIDATION_ERROR"
    DRIVER_ERROR = "DRIVER_ERROR"
    DATABASE_ERROR = "DATABASE_ERROR"
    API_ERROR = "API_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class ProbeError(Exception):
    """Base exception for all PROBE errors."""

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        detail: Optional[Any] = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.detail = detail

    def to_response(self) -> dict:
        """Safe representation — no raw stack traces."""
        payload: dict = {"error": self.code.value, "message": self.message}
        if self.detail is not None:
            payload["detail"] = self.detail
        return payload


class ValidationError(ProbeError):
    def __init__(self, message: str, detail: Optional[Any] = None) -> None:
        super().__init__(ErrorCode.VALIDATION_ERROR, message, detail)


class DriverError(ProbeError):
    def __init__(self, message: str, detail: Optional[Any] = None) -> None:
        super().__init__(ErrorCode.DRIVER_ERROR, message, detail)


class DatabaseError(ProbeError):
    def __init__(self, message: str, detail: Optional[Any] = None) -> None:
        super().__init__(ErrorCode.DATABASE_ERROR, message, detail)


class ApiError(ProbeError):
    def __init__(self, message: str, detail: Optional[Any] = None) -> None:
        super().__init__(ErrorCode.API_ERROR, message, detail)


class InternalError(ProbeError):
    def __init__(self, message: str, detail: Optional[Any] = None) -> None:
        super().__init__(ErrorCode.INTERNAL_ERROR, message, detail)
