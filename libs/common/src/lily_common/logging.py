"""Structured JSON logging for Lily services (NFR-19).

Every log line is a single JSON object carrying ``service``, ``trace_id``, and
``session_id``. Context values are bound per-request via contextvars so they
propagate through async call stacks without explicit plumbing. OTel exporters
arrive in Phase 4; until then ``trace_id`` is whatever the caller binds.
"""

from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

trace_id_var: ContextVar[str | None] = ContextVar("trace_id", default=None)
session_id_var: ContextVar[str | None] = ContextVar("session_id", default=None)

_RESERVED_ATTRS = frozenset(logging.LogRecord("", 0, "", 0, "", None, None).__dict__) | {
    "message",
    "asctime",
}


def bind_context(trace_id: str | None = None, session_id: str | None = None) -> None:
    """Bind request-scoped identifiers; they appear on every subsequent log line."""
    if trace_id is not None:
        trace_id_var.set(trace_id)
    if session_id is not None:
        session_id_var.set(session_id)


class JsonFormatter(logging.Formatter):
    def __init__(self, service: str) -> None:
        super().__init__()
        self._service = service

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "service": self._service,
            "message": record.getMessage(),
            "trace_id": trace_id_var.get(),
            "session_id": session_id_var.get(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        for key, value in record.__dict__.items():
            if key not in _RESERVED_ATTRS and not key.startswith("_"):
                payload[key] = value
        return json.dumps(payload, default=str)


def configure_logging(service: str, level: str = "INFO") -> None:
    """Install a JSON handler on the root logger. Idempotent per process."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter(service))
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
