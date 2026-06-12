"""Retrieval tools — hybrid BM25+kNN search over OpenSearch with catalog
enrichment. Clients (OpenSearch, Bedrock) and the psycopg connection are
injected. Bedrock embedding calls are wrapped in retry (A11 — throttles).
"""

from __future__ import annotations

from typing import Any

import psycopg

from lily_common.retry import call_with_retry, is_bedrock_transient
from lily_retrieval.models import (
    DiagnoseRequest,
    Diagnosis,
    LikelyPart,
    PartHit,
    SearchRequest,
    SymptomMatch,
)
from lily_search.embeddings import embed_text
from lily_search.index import hybrid_query, index_name

# catalog.symptom_parts has no ETL writer yet (parsers capture per-part
# symptoms_fixed but it isn't linked to the join table). diagnose_symptom is
# written against the table; until it's populated, likely_parts come back empty.
_SYMPTOM_PARTS_EMPTY_NOTE = (
    "Symptom-to-part links are not yet populated (catalog.symptom_parts is empty); "
    "ranked likely parts will appear once the ETL backfill lands."
)


def _embed(bedrock: Any, text: str) -> list[float]:
    return call_with_retry(lambda: embed_text(bedrock, text), retryable=is_bedrock_transient)


def search_parts(
    os_client: Any,
    bedrock: Any,
    conn: psycopg.Connection,
    request: SearchRequest,
    *,
    size: int = 5,
) -> list[PartHit]:
    """Hybrid search for parts by natural-language description (FR-9), enriched
    with current catalog price/stock."""
    vector = _embed(bedrock, request.text)
    body = hybrid_query(
        text=request.text, vector=vector, size=size, appliance_type=request.appliance_type
    )
    res = os_client.search(index=index_name("parts"), body=body)
    hits = res["hits"]["hits"]

    # Parts documents carry their ps_number so hits enrich from the live catalog.
    ps_numbers = [h["_source"]["ps_number"] for h in hits if "ps_number" in h["_source"]]
    enrich = _part_rows(conn, ps_numbers)
    out: list[PartHit] = []
    for h in hits:
        src = h["_source"]
        ps = src.get("ps_number", "")
        row = enrich.get(ps, {})
        out.append(
            PartHit(
                ps_number=ps,
                name=row.get("name") or src.get("title", ""),
                score=float(h["_score"]),
                price_usd=row.get("price_usd"),
                in_stock=row.get("in_stock"),
                image_url=row.get("image_url"),
                source_url=row.get("source_url") or src.get("source_url"),
            )
        )
    return out


def diagnose_symptom(
    os_client: Any,
    bedrock: Any,
    conn: psycopg.Connection,
    request: DiagnoseRequest,
    *,
    size: int = 3,
) -> Diagnosis:
    """Symptom-based diagnosis (FR-17): hybrid search the symptom corpus, then
    rank the parts that fix each match (model-filtered when a model is known)."""
    vector = _embed(bedrock, request.text)
    body = hybrid_query(
        text=request.text, vector=vector, size=size, appliance_type=request.appliance_type
    )
    res = os_client.search(index=index_name("symptoms"), body=body)

    matches: list[SymptomMatch] = []
    populated = False
    for h in res["hits"]["hits"]:
        src = h["_source"]
        parts = _likely_parts(conn, src["title"], request.appliance_type, request.model_number)
        populated = populated or bool(parts)
        matches.append(
            SymptomMatch(
                name=src["title"],
                score=float(h["_score"]),
                description=src.get("body"),
                source_url=src.get("source_url"),
                likely_parts=parts,
            )
        )
    note = None if populated else _SYMPTOM_PARTS_EMPTY_NOTE
    return Diagnosis(symptoms=matches, note=note)


_LIKELY_PARTS_SQL = """
SELECT pt.ps_number, pt.name, sp.fix_percentage
FROM catalog.symptoms s
JOIN catalog.symptom_parts sp ON sp.symptom_id = s.symptom_id
JOIN catalog.parts pt         ON pt.part_id = sp.part_id
WHERE s.name = %(name)s
  AND (%(appliance)s::text IS NULL OR s.appliance_type = %(appliance)s)
  AND (%(model)s::text IS NULL OR EXISTS (
        SELECT 1 FROM catalog.part_model_compatibility c
        JOIN catalog.models m ON m.model_id = c.model_id
        WHERE c.part_id = pt.part_id AND m.model_number_norm = catalog.norm_id(%(model)s)))
ORDER BY sp.fix_percentage DESC NULLS LAST, sp.display_rank NULLS LAST
LIMIT 5
"""


def _likely_parts(
    conn: psycopg.Connection, symptom_name: str, appliance: str | None, model: str | None
) -> list[LikelyPart]:
    with conn.cursor() as cur:
        cur.execute(
            _LIKELY_PARTS_SQL, {"name": symptom_name, "appliance": appliance, "model": model}
        )
        return [
            LikelyPart(ps_number=r[0], name=r[1], fix_percentage=_f(r[2])) for r in cur.fetchall()
        ]


_PART_ROWS_SQL = """
SELECT ps_number, name, price_usd, in_stock, image_url, source_url
FROM catalog.parts WHERE ps_number = ANY(%(ps)s)
"""


def _part_rows(conn: psycopg.Connection, ps_numbers: list[str]) -> dict[str, dict[str, Any]]:
    if not ps_numbers:
        return {}
    with conn.cursor() as cur:
        cur.execute(_PART_ROWS_SQL, {"ps": ps_numbers})
        return {
            r[0]: {
                "name": r[1],
                "price_usd": _f(r[2]),
                "in_stock": r[3],
                "image_url": r[4],
                "source_url": r[5],
            }
            for r in cur.fetchall()
        }


def _f(value: object) -> float | None:
    return None if value is None else float(value)  # type: ignore[arg-type]
