"""Structured JSON logging with the request ID on every line (structlog)."""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog

_CALENDAR_PREFIX = "/v1/calendar/"


def safe_path(path: str) -> str:
    """Calendar feed URLs carry a capability token in the path: never log it (AGENTS.md pitfalls)."""
    if path.startswith(_CALENDAR_PREFIX):
        return _CALENDAR_PREFIX + "[redacted]"
    return path


def configure_logging(level: str = "INFO") -> None:
    """Configure structlog to emit one JSON object per line to stdout. Safe to call more than once."""
    log_level = logging.getLevelNamesMapping().get(level.upper(), logging.INFO)
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=log_level, force=True)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=False,
    )


def get_logger(name: str | None = None, **initial: Any) -> Any:
    """A bound structlog logger. `name` becomes the `logger` field."""
    logger = structlog.get_logger(name)
    return logger.bind(logger=name, **initial) if name else logger.bind(**initial)
