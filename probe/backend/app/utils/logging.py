"""
Structured logging for PROBE.

All log records include: timestamp, level, component, event, test_id, metadata.
"""
import logging
import sys
from typing import Any

import structlog


def configure_logging() -> None:
    """Configure structlog for structured JSON-like output."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(colors=True),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.INFO,
    )


# Configure on import
configure_logging()


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a bound logger for the given component name."""
    return structlog.get_logger(name)


def bind_test_id(test_id: str) -> None:
    """Bind test_id to the current context for all subsequent log calls."""
    structlog.contextvars.bind_contextvars(test_id=test_id)


def clear_context() -> None:
    """Clear all bound context variables."""
    structlog.contextvars.clear_contextvars()
