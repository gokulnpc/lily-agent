"""First bounded live seed crawl — single-process orchestrator exercising the
full politeness machinery for real (robots + TTL + glob + fail-safe; token-bucket
rate limit; 403/429/5xx backoff; per-category budget with hard cap + drop
reporting). Two modes:

    python -m lily_etl.tools.seed_crawl discover  # persist the seed set; report queued/dropped
    python -m lily_etl.tools.seed_crawl fetch      # polite fetch -> S3 -> parse -> Aurora (two-hop)

Discovery uses appliance-scoped curated entry points: model URLs aren't
appliance-taggable from the sitemap, so the intentional seed is a small set of
fridge/dishwasher models (complete coverage) + their door/known part pages + the
two repair indexes. Sections are discovered from the model pages during fetch.
"""

from __future__ import annotations

import datetime
import os
import re
import sys
from typing import Any
from urllib.parse import urljoin

import boto3
import psycopg

from lily_common.robots import RobotsCache
from lily_common.s3keys import raw_key
from lily_crawler.browser import USER_AGENT, PoliteBrowser
from lily_crawler.budget import CrawlBudget
from lily_etl import upsert
from lily_parsers.dispatch import parse
from lily_parsers.dto import ParsedModel, ParsedPart, ParsedSection, ParsedSymptomIndex

BASE = "https://www.partselect.com"

# Curated, pre-verified entry points spanning 3 brands and both appliance types
# (all confirmed to have schematic /Sections/ pages — many newer models only
# have a flat parts list and aren't model-canonical-crawlable). A 6th candidate
# is seeded to keep demonstrating the drop-reporting cap.
CURATED_MODELS = [
    "/Models/WRS325FDAM04/",  # Whirlpool refrigerator (14 sections; has PS11752778)
    "/Models/WDT780SAEM1/",  # Whirlpool dishwasher (11)
    "/Models/LFSS2612TF0/",  # Frigidaire refrigerator (9)
    "/Models/GSS25GSHSS/",  # GE refrigerator (1)
    "/Models/GLD5604V00WW/",  # GE dishwasher (5)
    "/Models/WRX735SDHZ/",  # Whirlpool fridge — over the models=5 cap, drops
]
CURATED_PARTS = [
    "/PS11752778-Whirlpool-WPW10321304-Refrigerator-Door-Shelf-Bin.htm",
    "/PS11746591-Whirlpool-WPW10348269-Dishwasher-Door-Balance-Link-Kit.htm",
]
SYMPTOM_INDEXES = ["/Repair/Refrigerator/", "/Repair/Dishwasher/"]


def _budget() -> CrawlBudget:
    # Sized for 5 fully-covered models (~40 sections total) + headroom. Far
    # under the ~500 design cap; raised only as much as the extra models need.
    return CrawlBudget(target_models=5, models=5, sections=50, parts=8, symptoms=4)


def _robots(browser_session: Any) -> RobotsCache:
    # robots.txt is served as text/plain; Chrome wraps it in <pre>. Strip tags.
    def fetch_robots(url: str) -> str:
        html = browser_session.fetch(url).html
        return re.sub(r"<[^>]+>", "", html)

    return RobotsCache(fetcher=fetch_robots, user_agent=USER_AGENT)


def _db() -> psycopg.Connection:
    return psycopg.connect(os.environ["LILY_DATABASE_URL"] + "?connect_timeout=30")


def _seed_page(conn: psycopg.Connection, url: str, page_type: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO ingestion.source_pages (url, page_type, parse_status, discovered_at) "
            "VALUES (%s, %s, 'pending', now()) ON CONFLICT (url) DO NOTHING",
            (url, page_type),
        )
    conn.commit()


def discover() -> int:
    budget = _budget()
    queued: dict[str, int] = {}
    dropped: dict[str, int] = {}

    with PoliteBrowser().session() as session, _db() as conn:
        robots = _robots(session)
        candidates = (
            [(urljoin(BASE, u), "model") for u in CURATED_MODELS]
            + [(urljoin(BASE, u), "part") for u in CURATED_PARTS]
            + [(urljoin(BASE, u), "category") for u in SYMPTOM_INDEXES]
        )
        for url, page_type in candidates:
            if not robots.allowed(url):
                dropped[f"{page_type} (robots)"] = dropped.get(f"{page_type} (robots)", 0) + 1
                continue
            if not budget.try_spend(page_type):
                dropped[page_type] = dropped.get(page_type, 0) + 1
                print(f"  DROP {page_type} (budget cap): {url}", flush=True)
                continue
            _seed_page(conn, url, page_type)
            queued[page_type] = queued.get(page_type, 0) + 1

    print("\n=== DISCOVERY: queued (persisted to source_pages, status=pending) ===", flush=True)
    for pt, n in sorted(queued.items()):
        print(f"  {pt:10} {n}", flush=True)
    print("  queued models:", flush=True)
    with _db() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT url FROM ingestion.source_pages WHERE page_type='model' "
            "AND parse_status='pending' ORDER BY url"
        )
        for (mu,) in cur.fetchall():
            print(f"    {mu.replace(BASE, '')}", flush=True)
    print(
        f"  budget caps: models={budget.models} sections={budget.sections} "
        f"parts={budget.parts} symptoms={budget.symptoms}",
        flush=True,
    )
    print("=== DROPPED (hard cap / robots) ===", flush=True)
    print(f"  {dropped or 'none'}", flush=True)
    return 0


def _pending(conn: psycopg.Connection) -> list[tuple[str, str]]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT url, page_type FROM ingestion.source_pages "
            "WHERE parse_status = 'pending' ORDER BY page_type, url"
        )
        return [(r[0], r[1]) for r in cur.fetchall()]


def fetch() -> int:
    region = os.environ.get("AWS_REGION", "us-east-1")
    bucket = os.environ["LILY_RAW_BUCKET"]
    s3 = boto3.client("s3", region_name=region)
    today = datetime.date.today()
    budget = _budget()
    failures: list[tuple[str, str]] = []
    drift: list[str] = []
    fetched = 0

    with PoliteBrowser().session() as session, _db() as conn:
        robots = _robots(session)
        # In-memory work queue; model pages add their section URLs as discovered.
        work = _pending(conn)
        # account for already-seeded pages against the budget
        for _u, pt in work:
            budget.try_spend(pt)
        i = 0
        while i < len(work):
            url, page_type = work[i]
            i += 1
            if not robots.allowed(url):
                print(f"  SKIP robots: {url}", flush=True)
                continue
            resp = session.fetch(url)
            if resp.status != 200:
                failures.append((url, f"HTTP {resp.status}"))
                _mark(conn, url, "failed", f"HTTP {resp.status}")
                print(f"  FAIL [{resp.status}] {url}", flush=True)
                continue

            key = raw_key(page_type, url, today)
            s3.put_object(Bucket=bucket, Key=key, Body=resp.html.encode("utf-8"))
            fetched += 1
            try:
                spid = _spid(conn, url, page_type, key)
                result = parse(page_type, resp.html, url)
                _apply(conn, result, url, spid, budget, work)
                _mark(conn, url, "parsed", None)
                print(f"  OK  {page_type:8} {url.replace(BASE, '')}", flush=True)
            except Exception as exc:
                conn.rollback()
                msg = str(exc)[:200]
                if "schema drift" in msg.lower():
                    drift.append(f"{url}: {msg}")
                failures.append((url, msg))
                _mark(conn, url, "failed", msg)
                print(f"  PARSE-FAIL {url}: {msg}", flush=True)

    print(f"\n=== FETCH complete: {fetched} pages to S3 ===", flush=True)
    print(f"  failures: {len(failures)}", flush=True)
    for u, e in failures:
        print(f"    {e}  {u}", flush=True)
    print(f"  drift alerts: {drift or 'none'}", flush=True)
    return 0


def _spid(conn: psycopg.Connection, url: str, page_type: str, key: str) -> int:
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE ingestion.source_pages SET s3_key=%s, last_fetched_at=now() "
            "WHERE url=%s RETURNING source_page_id",
            (key, url),
        )
        row = cur.fetchone()
    conn.commit()
    assert row is not None
    return int(row[0])


def _apply(
    conn: psycopg.Connection,
    result: Any,
    url: str,
    spid: int,
    budget: CrawlBudget,
    work: list[tuple[str, str]],
) -> None:
    if isinstance(result, ParsedPart):
        upsert.upsert_part(conn, result, source_url=url, source_page_id=spid)
        conn.commit()
    elif isinstance(result, ParsedModel):
        upsert.upsert_model(conn, result, source_url=url, source_page_id=spid)
        conn.commit()
        # two-hop: discover this model's section pages (budget-capped)
        for section_url in result.section_urls:
            full = urljoin(BASE, section_url)
            if budget.try_spend("section"):
                _seed_page(conn, full, "section")
                work.append((full, "section"))
            else:
                print(f"  DROP section (budget cap): {full[:80]}", flush=True)
    elif isinstance(result, ParsedSection):
        with conn.cursor() as cur:
            cur.execute(
                "SELECT appliance_type FROM catalog.models "
                "WHERE model_number_norm = catalog.norm_id(%s)",
                (result.model_number,),
            )
            row = cur.fetchone()
        appliance = row[0] if row else "refrigerator"
        upsert.upsert_section_compat(
            conn, result, model_appliance_type=appliance, source_url=url, source_page_id=spid
        )
        conn.commit()
    elif isinstance(result, ParsedSymptomIndex):
        upsert.upsert_symptom_index(conn, result, source_url=BASE, source_page_id=spid)
        conn.commit()


def _mark(conn: psycopg.Connection, url: str, status: str, error: str | None) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE ingestion.source_pages SET parse_status=%s, parse_error=%s, "
            "last_parsed_at=now() WHERE url=%s",
            (status, error, url),
        )
    conn.commit()


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode == "discover":
        return discover()
    if mode == "fetch":
        return fetch()
    print("usage: python -m lily_etl.tools.seed_crawl {discover|fetch}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
