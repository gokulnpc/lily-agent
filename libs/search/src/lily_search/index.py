"""OpenSearch retrieval index: mapping, document body, and the hybrid BM25+kNN
query (D10). All pure dict builders — the query DSL is unit-tested without a
live domain. Index names live in the `retrieval-*` namespace so the single
domain can also hold `logs-*` later (D10 dual-duty).
"""

from __future__ import annotations

from typing import Any

from lily_search.embeddings import TITAN_V2_DIM

RETRIEVAL_PREFIX = "retrieval-"


def index_name(corpus: str) -> str:
    """e.g. corpus='guides' -> 'retrieval-guides'."""
    return f"{RETRIEVAL_PREFIX}{corpus}"


def retrieval_mapping(*, dim: int = TITAN_V2_DIM) -> dict[str, Any]:
    """Index settings + mapping: BM25 over text, kNN (HNSW/cosine) over the
    vector. `knn: true` enables the kNN plugin for this index."""
    return {
        "settings": {"index": {"knn": True, "number_of_shards": 1, "number_of_replicas": 0}},
        "mappings": {
            "properties": {
                "title": {"type": "text"},
                "body": {"type": "text"},
                "vector": {
                    "type": "knn_vector",
                    "dimension": dim,
                    "method": {
                        "name": "hnsw",
                        "space_type": "cosinesimil",
                        "engine": "lucene",
                    },
                },
                # filterable/displayable metadata
                "entity_type": {"type": "keyword"},
                "entity_id": {"type": "long"},
                "appliance_type": {"type": "keyword"},
                "source_url": {"type": "keyword"},
                "content_hash": {"type": "keyword"},
            }
        },
    }


def document(
    *,
    entity_type: str,
    entity_id: int,
    title: str,
    body: str,
    vector: list[float],
    appliance_type: str | None,
    source_url: str,
    content_hash: str,
) -> dict[str, Any]:
    return {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "title": title,
        "body": body,
        "vector": vector,
        "appliance_type": appliance_type,
        "source_url": source_url,
        "content_hash": content_hash,
    }


def hybrid_query(
    *,
    text: str,
    vector: list[float],
    k: int = 10,
    size: int = 5,
    appliance_type: str | None = None,
) -> dict[str, Any]:
    """Hybrid BM25 + kNN. BM25 matches title/body; kNN matches the vector; both
    contribute to the score (bool/should). An optional appliance filter scopes
    results (fridge vs dishwasher). Rerank/normalization is layered in Phase 2;
    this is the retrieval primitive."""
    should: list[dict[str, Any]] = [
        {"multi_match": {"query": text, "fields": ["title^2", "body"]}},
        {"knn": {"vector": {"vector": vector, "k": k}}},
    ]
    query: dict[str, Any] = {"bool": {"should": should, "minimum_should_match": 1}}
    if appliance_type is not None:
        query["bool"]["filter"] = [{"term": {"appliance_type": appliance_type}}]
    return {"size": size, "query": query}
