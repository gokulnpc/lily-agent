"""Catalog tools — typed functions over Aurora SQL. Each takes an injected
psycopg connection (the orchestrator owns the retry-wrapped connection via
lily_common.db.connect_with_retry). Parameterized queries only (NFR-14)."""

from __future__ import annotations

import psycopg

from lily_catalog.models import (
    CompatibilityRequest,
    CompatibilityResult,
    ModelSummary,
    PartDetails,
    PartSummary,
)

# The canonical four-verdict compatibility query (FR-13). norm_id() on both
# sides makes it robust to user formatting ("ps 11752778", "wrs-325...").
_COMPAT_SQL = """
SELECT
  CASE
    WHEN p.part_id  IS NULL     THEN 'PART_NOT_FOUND'
    WHEN m.model_id IS NULL     THEN 'MODEL_NOT_FOUND'
    WHEN c.part_id  IS NOT NULL THEN 'YES'
    ELSE 'NO'
  END AS verdict,
  p.ps_number, p.name, p.part_category,
  m.model_number, m.brand,
  c.source_url AS citation_url
FROM (SELECT 1) AS _
LEFT JOIN catalog.parts  p ON p.ps_number_norm    = catalog.norm_id(%(part)s)
LEFT JOIN catalog.models m ON m.model_number_norm = catalog.norm_id(%(model)s)
LEFT JOIN catalog.part_model_compatibility c
       ON c.part_id = p.part_id AND c.model_id = m.model_id
"""

# FR-14: on NO, the equivalent parts that fit this model. Same category as the
# part that failed (so we suggest the right kind of part), best-stocked first.
_ALTERNATIVES_SQL = """
SELECT pt.ps_number, pt.name, pt.part_category, pt.price_usd, pt.in_stock,
       pt.image_url, pt.source_url
FROM catalog.models m
JOIN catalog.part_model_compatibility c ON c.model_id = m.model_id
JOIN catalog.parts pt                   ON pt.part_id = c.part_id
WHERE m.model_number_norm = catalog.norm_id(%(model)s)
  AND (%(category)s::text IS NULL OR pt.part_category = %(category)s)
ORDER BY pt.in_stock DESC NULLS LAST, pt.rating_avg DESC NULLS LAST
LIMIT %(limit)s
"""


def check_compatibility(
    conn: psycopg.Connection, request: CompatibilityRequest, *, max_alternatives: int = 5
) -> CompatibilityResult:
    """Deterministic YES / NO / MODEL_NOT_FOUND / PART_NOT_FOUND (FR-13). On NO,
    populates `alternatives` with the equivalent fitting parts (FR-14)."""
    with conn.cursor() as cur:
        cur.execute(_COMPAT_SQL, {"part": request.part, "model": request.model})
        row = cur.fetchone()
    assert row is not None  # the (SELECT 1) base always yields exactly one row
    verdict, ps_number, part_name, part_category, model_number, brand, citation_url = row

    alternatives: list[PartSummary] = []
    if verdict == "NO":
        with conn.cursor() as cur:
            cur.execute(
                _ALTERNATIVES_SQL,
                {"model": request.model, "category": part_category, "limit": max_alternatives},
            )
            alternatives = [
                PartSummary(
                    ps_number=r[0],
                    name=r[1],
                    part_category=r[2],
                    price_usd=_f(r[3]),
                    in_stock=r[4],
                    image_url=r[5],
                    source_url=r[6],
                )
                for r in cur.fetchall()
            ]

    return CompatibilityResult(
        verdict=verdict,
        ps_number=ps_number,
        part_name=part_name,
        model_number=model_number,
        brand=brand,
        citation_url=citation_url,
        alternatives=alternatives,
    )


_PART_SQL = """
SELECT ps_number, name, appliance_type, mfr_part_number, brand, part_category,
       price_usd, stock_status, in_stock, install_difficulty, install_time,
       install_video_url, rating_avg, review_count, image_url, source_url
FROM catalog.parts WHERE ps_number_norm = catalog.norm_id(%(ps)s)
"""


def get_part_details(conn: psycopg.Connection, ps_number: str) -> PartDetails | None:
    """Full product-card fields for a part, or None if not in the catalog."""
    with conn.cursor() as cur:
        cur.execute(_PART_SQL, {"ps": ps_number})
        r = cur.fetchone()
    if r is None:
        return None
    return PartDetails(
        ps_number=r[0],
        name=r[1],
        appliance_type=r[2],
        mfr_part_number=r[3],
        brand=r[4],
        part_category=r[5],
        price_usd=_f(r[6]),
        stock_status=r[7],
        in_stock=r[8],
        install_difficulty=r[9],
        install_time=r[10],
        install_video_url=r[11],
        rating_avg=_f(r[12]),
        review_count=r[13],
        image_url=r[14],
        source_url=r[15],
    )


_FIND_MODELS_SQL = """
SELECT model_number, brand, appliance_type, name, source_url
FROM catalog.models
WHERE model_number_norm = catalog.norm_id(%(q)s)
   OR model_number ILIKE %(like)s
ORDER BY (model_number_norm = catalog.norm_id(%(q)s)) DESC, model_number
LIMIT %(limit)s
"""


def find_models(conn: psycopg.Connection, query: str, *, limit: int = 10) -> list[ModelSummary]:
    """Look up models by exact (normalized) match or partial number — for the
    'help me find my model number' flow."""
    with conn.cursor() as cur:
        cur.execute(_FIND_MODELS_SQL, {"q": query, "like": f"%{query}%", "limit": limit})
        return [
            ModelSummary(
                model_number=r[0], brand=r[1], appliance_type=r[2], name=r[3], source_url=r[4]
            )
            for r in cur.fetchall()
        ]


def _f(value: object) -> float | None:
    """psycopg returns NUMERIC as Decimal; the pydantic models expose float."""
    return None if value is None else float(value)  # type: ignore[arg-type]
