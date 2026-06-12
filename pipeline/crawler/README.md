# crawler

Discovery + fetchers (SQS-driven, Playwright/Chrome) writing raw HTML to
versioned S3. Politeness is mandatory: robots.txt, identified user-agent, rate
limits (D12/D13). **Phase 1.**

## Modules

| Module | Role |
|---|---|
| `urls.py` | URL classification (`part`/`model`/`section`/`symptom`/`category`) + appliance scoping. Pure. |
| `sitemap.py` | Sitemap-driven seed selection — bounded by a hard cap, robots-checked, appliance-scoped. The fetch + robots check are injected (offline-testable). |
| `fetcher.py` | Fetch-one control flow: robots re-check → fetch → **content-hash skip** or write raw HTML to S3 + enqueue parse. Every collaborator injected. |
| `browser.py` | Production Chrome-channel fetch with token-bucket pacing + 403/5xx backoff. The only Playwright touchpoint. |
| `aws.py` | boto3 S3/SQS adapters + psycopg `source_pages` store (skip/upsert/failure semantics). |
| `runner.py` | Pod entrypoints `discover` and `fetch-worker`. |
| `tools/capture_fixtures.py` | Polite developer utility to refresh the parser test fixtures. |

## Design invariants

- **Fetchers never parse.** Raw HTML → `raw/{page_type}/dt=YYYY-MM-DD/{sha256(url)}.html`
  in the versioned bucket; parsers read only from S3.
- **Model-canonical compatibility (A9):** discovery seeds appliance-classifiable
  **part** + **symptom** pages (model URLs aren't appliance-tagged). Models, then
  their **section** pages (`/Models/{n}/Sections/{s}/` — the robots-clean
  completeness path, not the `/Parts/` mega-list), are discovered downstream by
  the parsers. See docs/DECISIONS.md A9 + D12-crawler.
- **Scope:** sitemap-anchored, never link-walking; `LILY_SEED_CAP` (default 500)
  is a hard stop that reports drops. Widening = Phase 5 + owner confirm (D13).

## Run (pod)

```sh
python -m lily_crawler.runner discover       # sitemap -> crawl-jobs
python -m lily_crawler.runner fetch-worker    # crawl-jobs -> S3 + parse-jobs
```

Env: `LILY_CRAWL_QUEUE_URL`, `LILY_PARSE_QUEUE_URL`, `LILY_RAW_BUCKET`,
`LILY_DATABASE_URL` (ESO-synced), `LILY_SEED_CAP`.
