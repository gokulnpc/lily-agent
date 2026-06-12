# DECISIONS.md — Locked Architecture & Phase Plan

Status legend: **LOCKED** = do not change without owner sign-off · **OPEN** = needs owner input before implementing.

## Locked decisions

| # | Decision | Choice | Rationale (short) |
|---|---|---|---|
| D1 | LLM provider | Claude on AWS Bedrock (Converse API) | LOCKED. IAM-native auth, single AWS boundary |
| D2 | Model tiering | Haiku: guardrails/router/rewrites · Sonnet: specialist agents | LOCKED. Cost + latency |
| D3 | Embeddings | Titan Embeddings v2 via Bedrock | LOCKED |
| D4 | Orchestration | LangGraph; Redis checkpointer; tools framework-agnostic | LOCKED |
| D5 | Agent topology | input guardrail → intent router → specialists (Product/Compatibility/Repair/Order) → deterministic validator → output guardrail | LOCKED |
| D6 | Guardrails | Bedrock Guardrails (scope, PII) + custom Haiku classifier + deterministic part-number validator | LOCKED |
| D7 | Compute | EKS, real AWS. Namespaces: frontend, agent, commerce, data, observability, platform | LOCKED |
| D8 | Edge | Route53 → CloudFront → WAF → ALB ingress | LOCKED |
| D9 | Primary DB | Aurora PostgreSQL Serverless v2 (0.5 ACU floor) | LOCKED |
| D10 | Search/RAG + logs | One OpenSearch domain; separate index namespaces for retrieval vs logs; hybrid BM25+kNN | LOCKED |
| D11 | Cache/session | ElastiCache Redis: sessions, semantic cache (cosine ≥0.95 + intent match), rate limits | LOCKED |
| D12 | Ingestion | discovery → SQS → fetchers (Playwright/HTTP) → raw S3 (versioned) → parsers (read S3 only) → Aurora → embeddings → OpenSearch. Content-hash change detection, nightly incremental | LOCKED |
| D13 | Crawl scope (initial) | ~500 representative fridge+dishwasher pages; widen only in Phase 5 | LOCKED |
| D14 | Observability | OTel everywhere → Jaeger; Prometheus+Grafana; Fluent Bit → OpenSearch/Kibana; Alertmanager → notifications svc → SNS/Slack; Langfuse for LLM traces | LOCKED |
| D15 | IaC / CI | Terraform (modules + envs), GitHub Actions, ECR | LOCKED |
| D16 | Frontend | Next.js App Router, SSE streaming, PartSelect branding | LOCKED |
| D17 | Cost guards | Spot node groups (stateless), single NAT, overnight scale-down for non-prod, hourly LLM budget alert | LOCKED |
| D18 | Orders | Mock order service; no real payments; cart hands off to PartSelect checkout deep link | LOCKED |

## Open decisions (ask owner before implementing)
| # | Question |
|---|---|
| O1 | Crawl breadth at launch: all brands vs top-N by catalog size |
| O2 | Demo order data: seeded fixtures vs free-form mock |
| O3 | Langfuse self-hosted in-cluster vs Jaeger-only |
| O5 | Voice input (P2) in or out of demo scope |

## Resolved decisions
| # | Decision | Date |
|---|---|---|
| O4 | **GitHub Actions deploys only** in MVP — no Argo CD. `k8s/` stays pure app charts (Argo-compatible); Argo Rollouts considered for Phase 5 canaries. | 2026-06-11 |
| — | Dev region: **us-east-1** (Bedrock availability; ACM certs reusable for CloudFront). | 2026-06-11 |
| — | Phase 0 edge: ACM cert on ALB; **CloudFront + WAF deferred to Phase 3** (D8 target topology unchanged). See docs/adr/0001. | 2026-06-11 |
| D2 (amended) | Model tiering moved to **current generation: Haiku 4.5 (router/guardrails) + Sonnet 4.6 (specialists)**. The 3.5 generation is legacy-gated on Bedrock — `anthropic.claude-3-5-haiku` returns "upgrade to an active model" on invocation. Exact inference-profile IDs (from `aws bedrock list-inference-profiles`): router `global.anthropic.claude-haiku-4-5-20251001-v1:0` (the Global profile confirmed active in the account), specialists `global.anthropic.claude-sonnet-4-6`. On-demand bare model IDs aren't invocable — must use the inference profile (NFR-5 cross-region). Defaults in `services/orchestrator/.../converse.py`, env-overridable via `LILY_ROUTER_MODEL_ID` / `LILY_SPECIALIST_MODEL_ID`. | 2026-06-12 |
| D9 (amended) | Aurora Serverless v2 floor changed **0.5 ACU → 0 ACU with auto-pause** (10 min idle, ~15s cold resume). The 0-ACU feature postdates the original decision; D9's rationale was cost, and this is ~$40/mo cheaper for a dev cluster. Floor is the `aurora_min_acu` tfvar — raise it if cold starts ever matter. | 2026-06-12 |
| D12 (crawler) | **Compatibility pairs ingested model-page-only** (A9 model-canonical); part pages = attributes only. **Fetcher uses Playwright Chrome channel** (headless is Akamai-403'd) with identified UA, robots honored, rate-limited — access requirement, no proxies/spoofing. **Seed mix = complete models + the parts they reference + relevant symptom pages**, ~500 cap, sitemap-driven discovery (no link-walking). Widening = Phase 5 + owner confirm. | 2026-06-12 |

## Phase 0 hardening notes (2026-06-11)

Three failures hit during first platform bring-up; each fix is now in
`terraform/envs/dev/platform/main.tf` and verified by a clean destroy → single-pass
re-apply (112s):

| Fix | Failure it addresses |
|---|---|
| `atomic + cleanup_on_fail + wait` on every `helm_release` | A failed install stranded the release in `failed` state, blocking every retry until manual `helm uninstall`. Atomic installs roll back to nothing. |
| `depends_on = [helm_release.alb_controller]` on cert-manager and external-secrets | The ALB controller's **mutating webhook intercepts pod creation cluster-wide**. Charts installed concurrently with it raced its unready endpoints ("no endpoints available for service aws-load-balancer-webhook-service") and failed. Install the controller alone, then everything else. |
| ESO cert-controller readiness window widened (period 10s × threshold 12 ≈ 2 min) | The cert-controller reports ready only after provisioning the webhook TLS secret. Chart 2.6.0's default window (20s delay + 3×5s) is too tight on first install; the probe flapped and stalled `helm --wait` until timeout. |

Related convention (also in CLAUDE.md): admission webhooks and control-plane-critical
pods are pinned to the on-demand `system` node pool — a spot reclaim of a webhook pod
turns into cluster-wide admission failures. The chart-level `nodeSelector` does NOT
cover webhook/cainjector/cert-controller subcomponents; each needs its own pin.

## Phase 1 schema assumptions — VERIFY DURING CRAWLER STEP (2026-06-12)

The 0001 schema was designed without real PartSelect HTML in hand (the site 403s
plain fetchers). Each assumption below is hedged in the DDL (`db/migrations/0001_init.sql`)
but gets tested for real by the crawler/parser. **Update the Status column as real
pages confirm or refute each one; a refuted assumption gets an additive migration,
recorded here.**

| # | Assumption | Hedge in schema | Status |
|---|---|---|---|
| A14 | **symptom_parts can't be backfilled from part-page `symptoms_fixed`.** Discovered Phase 2 (2026-06-12): the part parser extracts `symptoms_fixed` but it is **never persisted** (no `catalog.parts` column; `upsert_part` drops it), the part-page vocabulary differs from the repair-index symptom names ("Ice maker won't dispense ice" vs canonical "Ice maker not making ice"), and only 2 part pages were crawled — so a `symptoms_fixed → symptoms.name` join links almost nothing. **The authoritative FR-17 source is the symptom DETAIL pages** (`/Repair/{appliance}/{symptom}/`, which list the parts that fix each symptom + fix %); no parser exists for them yet and they weren't crawled. **Deferred:** `catalog.symptom_parts` stays empty; `diagnose_symptom` returns matched symptoms + an explanatory note. Populating it (new symptom-detail parser + small crawl) is owned by the real Repair specialist (Phase 2 step 3+). | deferred |
| A1 | MPN uniqueness scope (global? per-brand?) | non-unique index on `mfr_part_number_norm`; MPN lookups may return multiple candidates, agent disambiguates | untested |
| A2 | `model_number` globally unique | `UNIQUE(model_number_norm)`; ETL logs conflicting-brand upserts as schema drift; fallback = unique(brand, model_number_norm) + disambiguation turn | untested |
| A3 | difficulty/time vocab ("Really Easy", "15-30 mins") | verbatim text, no CHECK, never branch on these | untested |
| A4 | one install video per part | single `install_video_url`; multiples ⇒ additive `part_videos` table | untested |
| A5 | fix % present per symptom-part pair | nullable + `display_rank` fallback ordering | untested |
| A6 | stock label vocabulary | raw `stock_status` text + parser-derived `in_stock` boolean; unknown ⇒ NULL ⇒ "check product page" | untested |
| A7 | qna/review shapes (no stable IDs, unanswered Qs, anon reviewers) | nearly all nullable; dedup via `UNIQUE(part_id, content_hash)` | untested |
| A8 | USD only; sale + list price | `price_usd` + nullable `list_price_usd`; no currency column | untested |
| A13 | **Coverage limitation: model-canonical crawling only reaches models that have schematic `/Sections/` pages.** Confirmed across brands during the widened crawl prep (2026-06-12): many *newer* models (e.g. Maytag MDB7749SBW, KitchenAid KUDS30IXSS, GE GDF520PGJWW, Frigidaire FFCD2413US) expose only a **flat parts list** (`/Models/{n}/Parts/`, the robots-discouraged mega-list) with **zero `/Sections/` pages**, so the section-based compatibility ingestion (A9) yields no pairs for them. Section-having models skew older, which also skews brand variety (Whirlpool/Frigidaire/GE had crawlable models in our checks). **Product boundary:** the agent can only answer compatibility for models in the catalog, and the catalog can only cover models with section pages via the current path. **Extension path:** add a second ingestion path that parses the flat parts list directly (from `/Models/{n}/Parts/` — would require revisiting the A9 deny-glob and the per-page janitor, since flat-list pairs would be sourced from the parts page, not a section). Until then, seed sets must use section-having models, and "model not found / not covered" is the honest answer for flat-list-only models. | active |
| A12 | **`Cover-Sheet` sections legitimately have no parts.** The first live crawl flagged every model's `/Sections/Cover-Sheet/` page as drift (`parts missing`) — these are the schematic *diagram cover* pages, not parts lists, so they correctly have zero parts. **RESOLVED 2026-06-12:** `section.py` has `KNOWN_EMPTY_SECTIONS = {cover-sheet}`; those slugs skip the `require(parts)` assertion and return empty parts (no alert), while genuine parts sections with a broken selector still raise `SchemaDriftError` (both behaviours tested). Add to the set if other no-parts section types are confirmed. | resolved |
| A11 | **Aurora 0-ACU cold start drops in-flight transactions.** With `min_capacity=0` (auto-pause), the first connection after idle triggers a ~15–60s resume; connections/queries during the resume window fail with `FATAL: the database system is starting up` or `SSL error: unexpected eof`. Confirmed 2026-06-12 during the indexing proof. **Every service that connects to Aurora must implement connection retry with backoff** (a warm-up SELECT or psycopg retry) — this is a Phase 2 requirement for gateway/catalog/orchestrator/etl, not optional. Raising the floor to 0.5 ACU avoids it at ~+$43/mo (we keep 0 for cost; retry is the right fix). | active |
| A10 | **Section URLs must keep their query string.** `/Models/{n}/Sections/{s}/` returns **HTTP 500** without the `?ModelID=…&ModelNum=…&Type=…` params present in the model page's section links. The model parser preserves the full href (query included); the fetcher must not strip it. A future "URL cleanup" that drops query strings would silently break section fetching (the compat completeness path). Verified 2026-06-12: bare section URL → 500, full URL → 200. | active |
| A9 | **Compatibility directionality**: does PartSelect list compatible models on part pages, compatible parts on model pages, or both — and which side is complete? | The table is direction-agnostic (a pair observed on whatever page), but the per-page staleness janitor assumes **one canonical ingestion direction**: a pair carries one `source_page_id`, so ingesting the same pair from both directions makes page A's janitor able to delete a pair still live on page B. | **RESOLVED 2026-06-12 — model-canonical.** Both directions exist (verified on real HTML): part pages list models, model pages list parts, and a sampled pair cross-attests. BUT the part→models list is **paginated/incomplete per fetch** (PS11752778 page 1 = first 30 Kenmore models, omits a known-compatible Whirlpool model on a later page), while the model→parts list is **bounded and complete per model page**. Decision: **compatibility pairs are ingested ONLY from model pages** (one `source_page_id` per pair, janitor sound); part pages supply attributes only and their cross-reference is ignored for pair ingestion. Enforced as a parser rule — **no schema change to 0001**. |

## Phases & exit criteria (work strictly in order)

| Phase | Scope | Exit criteria — stop and review here |
|---|---|---|
| 0 | Monorepo scaffold; Terraform bootstrap (state backend, VPC, EKS, ECR, IRSA); platform namespace (ingress, cert-manager, external-secrets); CI skeleton; local compose profile | `terraform apply` clean; hello-world pod behind TLS ingress; `make check` green |
| 1 | Aurora schema (parts, models, part_model_compatibility, repair_guides, qna, orders); crawler+parsers on ~500 seed pages; S3/SQS plumbing; OpenSearch indexing | Compatibility answerable via SQL; hybrid search returns relevant guides; pipeline dashboard panels live |
| 2 | LangGraph graph, tools, guardrails, Redis memory, FastAPI SSE gateway | 3 brief examples + 20 eval cases pass via curl; traces visible in Jaeger |
| 3 | Next.js chat UI: streaming, product cards, quick replies, feedback | E2E demo on real data |
| 4 | Full observability: 5 Grafana dashboards, Kibana logs, Alertmanager→Slack, Langfuse (if O3=yes) | One trace end-to-end; test alert fires in Slack |
| 5 | 100-case eval suite as CI gate; semantic cache; crawl widening; canary deploys; admin views | CI eval gate green; cost dashboard live |

## Reference
- Inspiration repo (do NOT copy architecture): https://github.com/zehuiwu/partselect-agent
- Case-study brief: docs/PRD.md §1, §10
