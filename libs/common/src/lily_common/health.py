"""Reusable health endpoints. Mounted by every Lily service."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    """Liveness: the process is up and serving."""
    return {"status": "ok"}


@router.get("/readyz")
async def readyz() -> dict[str, str]:
    """Readiness: safe to receive traffic. Services override with dependency checks."""
    return {"status": "ready"}
