"""structlog-based logging configured for JSON (production) or console (dev).

Design notes
------------
* Every log line inherits `request_id` from a contextvar, so async handlers,
  middleware, and graph nodes all stamp logs without manual plumbing.
* `configure_logging` is idempotent and safe to call from tests.
* Stdlib loggers (uvicorn, openai, anthropic, langgraph) are routed through
  the same renderer so third-party logs become JSON and inherit request_id.
"""

from __future__ import annotations

import logging
import sys
from contextvars import ContextVar
from typing import Any

import structlog
from structlog.types import EventDict, Processor

from app.config import Settings

_request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)


# ----------------------------------------------------------------------------
# Request-id helpers (call at the request boundary in FastAPI middleware)
# ----------------------------------------------------------------------------
def bind_request_id(request_id: str) -> None:
    """Bind a request_id to the current async context."""
    _request_id_ctx.set(request_id)
    structlog.contextvars.bind_contextvars(request_id=request_id)


def clear_request_id() -> None:
    """Clear request-scoped logging context."""
    _request_id_ctx.set(None)
    structlog.contextvars.clear_contextvars()


def get_request_id() -> str | None:
    return _request_id_ctx.get()


def _add_request_id(_logger: Any, _method: str, event_dict: EventDict) -> EventDict:
    rid = _request_id_ctx.get()
    if rid is not None and "request_id" not in event_dict:
        event_dict["request_id"] = rid
    return event_dict


# ----------------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------------
def configure_logging(settings: Settings) -> None:
    """Configure stdlib logging + structlog. Safe to call multiple times."""
    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    # `force=True` lets tests reconfigure cleanly between cases.
    logging.basicConfig(
        level=level,
        format="%(message)s",
        stream=sys.stdout,
        force=True,
    )

    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        _add_request_id,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    renderer: Processor = (
        structlog.dev.ConsoleRenderer(colors=True)
        if settings.log_format == "console"
        else structlog.processors.JSONRenderer()
    )

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> Any:
    """Return a structlog logger.

    Annotated as `Any` because the runtime type depends on configuration
    (`make_filtering_bound_logger` produces a dynamic class); the duck-typed
    surface (`.info`, `.error`, `.bind`, `.warning`) is what callers use.
    """
    return structlog.get_logger(name) if name else structlog.get_logger()
