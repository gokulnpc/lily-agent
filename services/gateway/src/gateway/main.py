"""Gateway entrypoint.

Phase 0: health stub proving the build → ECR → Helm → ALB → TLS path.
Phase 2 replaces this with the SSE chat endpoint in front of the orchestrator.
"""

from __future__ import annotations

from fastapi import FastAPI

from gateway import __version__
from lily_common.health import router as health_router
from lily_common.logging import configure_logging


def create_app() -> FastAPI:
    configure_logging(service="gateway")
    app = FastAPI(title="Lily Gateway", version=__version__)
    app.include_router(health_router)

    @app.get("/")
    async def root() -> dict[str, str]:
        return {"service": "gateway", "version": __version__}

    return app


app = create_app()
