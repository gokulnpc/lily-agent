"""Gateway entrypoint.

Phase 0: health stub proving the build → ECR → Helm → ALB → TLS path.
Phase 2 (step 5): the SSE chat endpoint in front of the embedded orchestrator.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.responses import StreamingResponse

from gateway import __version__, telemetry
from gateway.chat import ChatRequest, stream_chat
from gateway.feedback import FeedbackRequest, record_feedback
from lily_common.health import router as health_router
from lily_common.logging import bind_context, configure_logging


def create_app(*, graph: Any | None = None) -> FastAPI:
    """Build the app. Tests inject a pre-built `graph` (FakeConverse +
    MemorySaver); in prod it's lazily built from env on the first chat turn so
    health checks and imports need no AWS/DB."""
    configure_logging(service="gateway")
    telemetry.setup_tracing(service="gateway")
    app = FastAPI(title="Lily Gateway", version=__version__)
    app.include_router(health_router)
    app.state.graph = graph

    @app.get("/")
    async def root() -> dict[str, str]:
        return {"service": "gateway", "version": __version__}

    @app.get("/metrics")
    async def metrics() -> Response:
        body, content_type = telemetry.metrics_response()
        return Response(content=body, media_type=content_type)

    @app.post("/feedback", status_code=204)
    async def feedback(req: FeedbackRequest) -> Response:
        record_feedback(req)
        return Response(status_code=204)

    @app.post("/chat")
    async def chat(req: ChatRequest, request: Request) -> StreamingResponse:
        graph_obj = request.app.state.graph
        if graph_obj is None:
            from gateway.graph_runner import build_prod_graph

            graph_obj = request.app.state.graph = await build_prod_graph()
        trace_id = uuid.uuid4().hex
        bind_context(trace_id=trace_id, session_id=req.session_id)
        return StreamingResponse(
            stream_chat(
                graph_obj, session_id=req.session_id, message=req.message, trace_id=trace_id
            ),
            media_type="text/event-stream",
            headers={"x-trace-id": trace_id, "cache-control": "no-cache"},
        )

    return app


app = create_app()
