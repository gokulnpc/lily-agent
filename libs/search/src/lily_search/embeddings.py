"""Titan Embeddings v2 via Bedrock (D3). The Bedrock client is injected so the
embedding shape/flow is testable without AWS."""

from __future__ import annotations

import json
from typing import Any

TITAN_V2_MODEL_ID = "amazon.titan-embed-text-v2:0"
TITAN_V2_DIM = 1024  # default output dimension for Titan v2


def embed_text(client: Any, text: str, *, model_id: str = TITAN_V2_MODEL_ID) -> list[float]:
    """Return the embedding vector for `text`. Raises on empty input (never
    embed nothing — that would poison kNN)."""
    if not text or not text.strip():
        raise ValueError("cannot embed empty text")
    response = client.invoke_model(
        modelId=model_id,
        body=json.dumps({"inputText": text}),
        contentType="application/json",
        accept="application/json",
    )
    payload = json.loads(response["body"].read())
    vector: list[float] = payload["embedding"]
    return vector
