"""Per-message feedback endpoint (FR-25) — offline."""

from __future__ import annotations

from fastapi.testclient import TestClient

from gateway import telemetry
from gateway.main import create_app


def test_feedback_records_and_returns_204() -> None:
    client = TestClient(create_app(graph=object()))
    before = telemetry.FEEDBACK.labels(rating="up")._value.get()
    resp = client.post(
        "/feedback",
        json={"trace_id": "abc123", "session_id": "s1", "rating": "up", "comment": "spot on"},
    )
    assert resp.status_code == 204
    assert telemetry.FEEDBACK.labels(rating="up")._value.get() == before + 1


def test_feedback_rejects_bad_rating() -> None:
    client = TestClient(create_app(graph=object()))
    resp = client.post("/feedback", json={"trace_id": "x", "session_id": "s", "rating": "meh"})
    assert resp.status_code == 422  # Literal["up","down"] validation
