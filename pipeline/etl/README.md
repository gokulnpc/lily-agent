# etl

Normalize parsed records into Aurora; mark changed entities for embedding into
OpenSearch. Content-hash change detection; nightly incremental. **Phase 1.**

## Modules

| Module | Role |
|---|---|
| `upsert.py` | Parsed DTOs → Aurora rows. Parts/models upsert on their natural key; **compatibility is model-canonical (A9)** — pairs written only from section pages, plus the per-page staleness janitor. |
| `index_jobs.py` | `ingestion.search_sync` bookkeeping — marks changed entities `stale` and enqueues an index job; skips unchanged-and-indexed rows so the embed job never re-embeds (NFR-7). Queue injected. |
| `runner.py` | Worker: drain parse-jobs → read raw HTML **from S3** → parse → upsert → enqueue section discovery + index jobs. Never re-fetches the site. |

## Staleness janitor

Upserts bump `last_seen_at = now()`. After a section's pairs are re-applied,
`upsert_section_compat` deletes that section page's pairs whose
`last_seen_at < now()` — the ones that vanished from the re-parsed page — all in
**one transaction** (so `now()` is the transaction start: re-seen pairs survive,
vanished pairs sourced from an earlier transaction are pruned). A failed crawl
can never mass-delete; the prune is scoped to the one section's `source_page_id`.

Pruning a pair ages out the *fitment*, not the part — the `catalog.parts` row
survives (it's still a real part), the compatibility answer just flips to NO.

## Run (pod)

```sh
python -m lily_etl.runner   # drain parse-jobs -> Aurora + crawl/index jobs
```

Env: `LILY_DATABASE_URL`, `LILY_RAW_BUCKET`, `LILY_PARSE_QUEUE_URL`,
`LILY_CRAWL_QUEUE_URL`, `LILY_INDEX_QUEUE_URL`.
