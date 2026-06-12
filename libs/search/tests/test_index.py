"""Pure builders — mapping, document, and the hybrid query DSL — offline."""

from __future__ import annotations

import json

from lily_search.embeddings import TITAN_V2_DIM, embed_text
from lily_search.index import (
    document,
    hybrid_query,
    index_name,
    retrieval_mapping,
)


def test_index_namespace() -> None:
    assert index_name("guides") == "retrieval-guides"
    assert index_name("symptoms").startswith("retrieval-")


def test_mapping_has_knn_vector_and_text() -> None:
    m = retrieval_mapping()
    assert m["settings"]["index"]["knn"] is True
    props = m["mappings"]["properties"]
    assert props["vector"]["type"] == "knn_vector"
    assert props["vector"]["dimension"] == TITAN_V2_DIM
    assert props["vector"]["method"]["space_type"] == "cosinesimil"
    assert props["body"]["type"] == "text"


def test_hybrid_query_combines_bm25_and_knn() -> None:
    q = hybrid_query(text="ice maker not working", vector=[0.1] * 4, k=10, size=5)
    should = q["query"]["bool"]["should"]
    kinds = {next(iter(clause)) for clause in should}
    assert kinds == {"multi_match", "knn"}  # both retrieval modes present
    assert q["size"] == 5
    bm25 = next(c for c in should if "multi_match" in c)["multi_match"]
    assert bm25["query"] == "ice maker not working"
    assert "title^2" in bm25["fields"]


def test_hybrid_query_appliance_filter() -> None:
    q = hybrid_query(text="x", vector=[0.0], appliance_type="refrigerator")
    assert q["query"]["bool"]["filter"] == [{"term": {"appliance_type": "refrigerator"}}]
    # no filter when unscoped
    assert "filter" not in hybrid_query(text="x", vector=[0.0])["query"]["bool"]


def test_document_shape() -> None:
    doc = document(
        entity_type="symptom",
        entity_id=7,
        title="Ice maker not making ice",
        body="...",
        vector=[0.1, 0.2],
        appliance_type="refrigerator",
        source_url="https://x/Repair/Refrigerator/Not-Making-Ice/",
        content_hash="h1",
    )
    assert doc["entity_id"] == 7
    assert doc["vector"] == [0.1, 0.2]
    assert doc["content_hash"] == "h1"


# --- embeddings (fake Bedrock client, no AWS) -------------------------------


class FakeBedrock:
    def __init__(self, vector: list[float]) -> None:
        self._vector = vector
        self.calls: list[str] = []

    def invoke_model(self, *, modelId: str, body: str, **_: object) -> dict[str, object]:
        self.calls.append(json.loads(body)["inputText"])

        class _Body:
            def __init__(self, payload: bytes) -> None:
                self._p = payload

            def read(self) -> bytes:
                return self._p

        return {"body": _Body(json.dumps({"embedding": self._vector}).encode())}


def test_embed_text_returns_vector() -> None:
    client = FakeBedrock([0.5, 0.25, 0.125])
    vec = embed_text(client, "ice maker not working")
    assert vec == [0.5, 0.25, 0.125]
    assert client.calls == ["ice maker not working"]


def test_embed_rejects_empty() -> None:
    import pytest

    with pytest.raises(ValueError):
        embed_text(FakeBedrock([0.1]), "   ")
