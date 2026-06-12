"""Per-message feedback (FR-25): 👍/👎 keyed to the turn's trace_id. Stored as a
structured log line (Fluent Bit → OpenSearch/Kibana mines it in Phase 4) + a
Prometheus counter. Durable storage / Langfuse linkage is Phase 4."""

from __future__ import annotations

import logging
from typing import Literal

from pydantic import BaseModel

from gateway import telemetry

log = logging.getLogger("gateway.feedback")


class FeedbackRequest(BaseModel):
    trace_id: str
    session_id: str
    rating: Literal["up", "down"]
    comment: str | None = None


def record_feedback(req: FeedbackRequest) -> None:
    telemetry.FEEDBACK.labels(rating=req.rating).inc()
    # trace_id/session_id ride the structured JSON formatter (lily_common.logging);
    # comment is included for eval mining. No PII expected in a 👍/👎.
    log.info(
        "feedback",
        extra={
            "trace_id": req.trace_id,
            "session_id": req.session_id,
            "rating": req.rating,
            "comment": req.comment,
        },
    )
