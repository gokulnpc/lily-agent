"""build_prod_graph() — the seam (D4/D5 amended). The orchestrator is embedded in
the gateway process, but everything it needs is injected here from env, so moving
it to its own service later is a deploy change, not a refactor. Offline tests
never call this — they build the graph with a FakeConverse + MemorySaver directly.
"""

from __future__ import annotations

import os
from typing import Any

from lily_common.db import connect_with_retry


async def build_prod_graph() -> Any:
    """Wire the live graph from env: Aurora (A11 retry), Bedrock, OpenSearch, the
    guardrail id/version, and an async Redis checkpointer keyed by session_id.
    Async because the checkpointer's index setup (RediSearch) is async — and the
    SSE path drives the graph with astream, which needs the async checkpointer.

    NOTE (dev/demo scale): one DB connection backs the graph. A per-request pool
    is prod hardening (tracked for the deploy step), not needed for the Phase-2
    exit demo.
    """
    import boto3  # local import keeps module import cheap (health checks, tests)

    from lily_orchestrator.graph import build_graph
    from lily_orchestrator.specialists import Deps

    region = os.environ.get("AWS_REGION", "us-east-1")
    conn = connect_with_retry(os.environ["LILY_DATABASE_URL"])
    bedrock = boto3.client("bedrock-runtime", region_name=region)

    os_client = None
    endpoint = os.environ.get("LILY_OPENSEARCH_ENDPOINT")
    if endpoint:
        from lily_search.client import opensearch_client

        os_client = opensearch_client(endpoint, region=region)

    deps = Deps(
        conn=conn,
        bedrock=bedrock,
        os_client=os_client,
        guardrail_id=os.environ.get("LILY_GUARDRAIL_ID"),
        guardrail_version=os.environ.get("LILY_GUARDRAIL_VERSION", "DRAFT"),
    )
    return build_graph(deps=deps, checkpointer=await _checkpointer())


async def _checkpointer() -> Any:
    """Async Redis checkpointer (D11) keyed by thread_id=session_id, on Redis Stack
    (RediSearch). Falls back to an in-memory saver when no Redis is configured."""
    redis_url = os.environ.get("LILY_REDIS_URL")
    if redis_url:
        from langgraph.checkpoint.redis.aio import AsyncRedisSaver

        saver = AsyncRedisSaver(redis_url)
        await saver.asetup()
        return saver
    from langgraph.checkpoint.memory import MemorySaver

    return MemorySaver()
