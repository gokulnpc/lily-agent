"""Deterministic catalog fixture for the offline eval gate (evals/run.py).

A tiny, fully-controlled catalog so the compatibility verdicts are a known truth
table: parts + models + the EXACT compatibility pairs that make YES / NO /
MODEL_NOT_FOUND / PART_NOT_FOUND deterministic. Delete-then-insert on the eval's
own identifiers so it's idempotent and independent of any crawl data already in
the dev database. Orders come from migration 0007 (demo orders); symptoms/retrieval
are OpenSearch-backed and exercised only in the live tier.

`SRC` is the citation URL every seeded row carries (FR-19 assertions check it).
"""

from __future__ import annotations

import psycopg

SRC = "https://www.partselect.com/eval-fixture"

# (ps_number, name, appliance, category, price, in_stock, rating, reviews,
#  difficulty, time, video_url, mfr_part_number)
_PARTS = [
    (
        "PS11752778",
        "Refrigerator Door Shelf Bin",
        "refrigerator",
        "Door Bin",
        36.08,
        True,
        4.8,
        120,
        "Really Easy",
        "Less than 15 mins",
        "https://www.youtube.com/watch?v=eval1",
        "WPW10321304",
    ),
    (
        "PS10065979",
        "Refrigerator Door Shelf Bin (compatible alt)",
        "refrigerator",
        "Door Bin",
        41.50,
        True,
        4.6,
        64,
        "Really Easy",
        "Less than 15 mins",
        None,
        "W10451874",
    ),
    (
        "PS11722128",
        "Dishwasher Lower Spray Arm",
        "dishwasher",
        "Spray Arm",
        24.99,
        True,
        4.7,
        88,
        "Easy",
        "15 - 30 mins",
        None,
        "W10810400",
    ),
    (
        "PS8689951",
        "Dishwasher Spray Arm (older revision)",
        "dishwasher",
        "Spray Arm",
        19.50,
        False,
        4.1,
        12,
        None,
        None,
        None,
        "W10056351",
    ),
    (
        "PS11746142",
        "Dishwasher Door Gasket",
        "dishwasher",
        "Gasket",
        42.12,
        True,
        5.0,
        7,
        "Really Easy",
        "Less than 15 mins",
        None,
        "WP8531743",
    ),
]

# (model_number, brand, appliance, name)
_MODELS = [
    ("WRS325SDHZ", "Whirlpool", "refrigerator", "Side-by-Side Refrigerator"),
    ("WDT780SAEM1", "Whirlpool", "dishwasher", "Built-In Dishwasher"),
]

# Compatibility PAIRS that exist (everything else is NO):
#   PS11752778 + WRS325SDHZ  -> YES (fridge bin fits fridge)
#   PS10065979 + WRS325SDHZ  -> YES (alt fridge bin fits fridge)
#   PS11722128 + WDT780SAEM1 -> YES (spray arm fits dishwasher)
#   PS11746142 + WDT780SAEM1 -> YES (gasket fits dishwasher)
# Deliberately ABSENT (so the verdict is NO with a same-category alternative):
#   PS8689951 + WDT780SAEM1  -> NO, alternative = PS11722128 (Spray Arm that fits)
_PAIRS = [
    ("PS11752778", "WRS325SDHZ"),
    ("PS10065979", "WRS325SDHZ"),
    ("PS11722128", "WDT780SAEM1"),
    ("PS11746142", "WDT780SAEM1"),
]


def seed_catalog(conn: psycopg.Connection) -> None:
    ps_numbers = [p[0] for p in _PARTS]
    model_numbers = [m[0] for m in _MODELS]
    with conn.cursor() as cur:
        # Delete-then-insert on the eval's own ids (idempotent; crawl data untouched).
        cur.execute(
            "DELETE FROM catalog.part_model_compatibility WHERE part_id IN "
            "(SELECT part_id FROM catalog.parts WHERE ps_number = ANY(%s))",
            (ps_numbers,),
        )
        cur.execute("DELETE FROM catalog.parts WHERE ps_number = ANY(%s)", (ps_numbers,))
        cur.execute("DELETE FROM catalog.models WHERE model_number = ANY(%s)", (model_numbers,))

        for ps, name, app, cat, price, stock, rating, reviews, diff, time_, vid, mpn in _PARTS:
            cur.execute(
                "INSERT INTO catalog.parts (ps_number, name, appliance_type, part_category,"
                " price_usd, in_stock, rating_avg, review_count, install_difficulty,"
                " install_time, install_video_url, mfr_part_number, source_url, scraped_at)"
                " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s, now())",
                (ps, name, app, cat, price, stock, rating, reviews, diff, time_, vid, mpn, SRC),
            )
        for model, brand, app, name in _MODELS:
            cur.execute(
                "INSERT INTO catalog.models (model_number, brand, appliance_type, name,"
                " source_url, scraped_at) VALUES (%s,%s,%s,%s,%s, now())",
                (model, brand, app, name, SRC),
            )
        for ps, model in _PAIRS:
            cur.execute(
                "INSERT INTO catalog.part_model_compatibility (part_id, model_id, source_url)"
                " SELECT p.part_id, m.model_id, %s FROM catalog.parts p, catalog.models m"
                " WHERE p.ps_number = %s AND m.model_number = %s",
                (SRC, ps, model),
            )
    # NO commit: the graph + tools share this connection, so they see the seed
    # within the transaction. The runner rolls back at the end -> zero residue,
    # so the eval never collides with the unit tests' own committed fixtures.
