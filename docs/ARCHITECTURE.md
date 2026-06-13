# Architecture

The deep version. Companion to [README.md](../README.md) (the front door),
[DECISIONS.md](DECISIONS.md) (the locked decisions + assumption ledger), and
[WINS-LOG.md](WINS-LOG.md) (the measured build record). Every claim here is traceable to one
of those or to the code under `services/`, `pipeline/`, `terraform/`, `k8s/`.

## 1. The three planes

- **Edge / app plane** — Route53 → shared ALB → Next.js chat UI (`frontend` ns) and the SSE
  gateway (`agent` ns). The UI proxies `/chat` **cluster-internally** to the gateway, so the
  SSE stream stays same-origin (no public CORS).
- **Agent plane** — a LangGraph supervisor graph embedded in the gateway process: input
  guardrail → router (Haiku) → specialists (Sonnet) → deterministic validator → output
  guardrail, with a Redis checkpointer for session memory.
- **Data plane** — Aurora PostgreSQL (parts/models/compatibility/symptoms/orders), OpenSearch
  (hybrid retrieval + the `lily-logs-*` log index), ElastiCache-style in-cluster Redis
  (sessions), S3 (raw crawl), SQS (crawl/index jobs). Private subnets; reachable only from the
  cluster SG (proven by a negative test — [WINS](WINS-LOG.md): Aurora not internet-reachable).

D5 topology is LOCKED; the orchestrator is **embedded in the gateway** for dev scale, behind a
`build_prod_graph()` factory that preserves the split-out seam (§11).

## 2. The agent graph, node by node

`services/orchestrator/src/lily_orchestrator/graph.py` assembles the StateGraph. Each node is a
plain function over a `GraphState` TypedDict; the only framework dependency is the wiring.

1. **`entry`** — resets per-turn output fields (so cards/citations/intent can't bleed across
   turns via the checkpointer — a bug the live exit proof caught), then resolves entities from
   the utterance: PS/model numbers, email, order number. Session fields (`current_part`,
   `current_model`, `order_*`) persist via the checkpointer; a pronoun ("this part") with no new
   entity keeps the session value (FR-5). An order number is model-shaped, so it's compared
   against the model token in **normalized** form and kept out of `current_model`.
2. **`input_guardrail`** (D6) — Bedrock Guardrails (PROMPT_ATTACK + PII **anonymize**) then a
   Haiku **scope gate**. A block short-circuits to one polite decline (no router, no specialist
   LLM call, visible in the trace). PII (order#/email) is resolved in `entry` *before* the
   guardrail and fed only to the deterministic order tool — the model and the rendered response
   see masked values (NFR-13). The Bedrock **topic** policy was dropped after it false-positived
   on legitimate brand+model questions; the Haiku gate is the accurate scope arbiter.
3. **`router`** (Haiku 4.5) — classifies into `product / compatibility / repair / order /
   out_of_scope`, possibly multiple. First pass classifies; later passes carry the remaining intent.
4. **`specialist`** (Sonnet 4.6) — dispatches to exactly one specialist for the primary intent.
   Each specialist calls **only its own typed tools** (the allowlist is structural, not prompted),
   gets the tool result, and asks Sonnet to narrate it grounded. It accumulates `citations`,
   `tool_identifiers` (the validator's trust set), `structured` cards, and `quick_replies` —
   all built **structurally from tool results**, never parsed from prose. A bounded loop
   (`MAX_PASSES = 2`) returns to the router for a second intent; **`primary_intent` ends as the
   last intent processed** (the message payload's `trace` lists every `specialist:<intent>`).
5. **`validator`** (FR-4, deterministic) — extracts every PS/model-shaped token from the response
   and flags any not in `(tool_identifiers this turn ∪ catalog parts.ps/mfr ∪ models)`. Grounding
   guarantees the LLM only echoes tool-sourced ids, so a flag means a real problem. Strict by
   invariant: **no unvalidated identifier ever renders** — not-found messages don't echo the
   user's unverified id.
6. **`output_guardrail`** — Bedrock PII pass + a Haiku **topicality** backstop; an off-topic
   response is replaced by the safe decline.
7. **`save`** — terminal; the checkpointer persists session state.

**Specialist behaviors worth knowing:** compatibility returns the four-verdict result + (on `NO`)
deterministic alternatives; product handles by-PS, search, and the FR-11 comparison path (≥2 PS +
"compare"); repair splits into a symptom-diagnosis path (OpenSearch RAG) and an **install path**
(`get_install_info` — difficulty/time/video, gated on an install cue so a lingering session part
can't hijack a symptom turn); order calls the anti-enumeration `get_order` (uniform
`ORDER_NOT_FOUND` for wrong-email and nonexistent-order, emails masked).

### Model tiering (D2, amended)
Claude on Bedrock via the **Converse API**, cross-region inference profiles (NFR-5): **Haiku 4.5**
for guardrails/router/rewrites, **Sonnet 4.6** for specialists. Model IDs are env-overridable
defaults, so a forced generation swap (3.5 Haiku was legacy-gated live) is config, not code. A
single turn is ~3 Haiku calls + 1 Sonnet call — visible in the Jaeger trace and the ~$0.008 cost.

## 3. The wire contract (SSE + cards)

`services/gateway/src/gateway/chat.py`. The `/chat` SSE vocabulary:

- **`status`** — one per meaningful graph node as it completes (`{node, label}`), e.g.
  "Checking compatibility…". Carries perceived latency.
- **`message`** — the final assistant turn, sent **only after the validator + output guardrail**:
  `{text, primary_intent, blocked, invalid_identifiers, citations, structured, quick_replies,
  current_model, trace}`.
- **`done`** — `{session_id, trace_id}`; `trace_id` is also an `x-trace-id` response header.
- **`error`** — a safe user-facing line carrying `trace_id`.

**No token-level delta event, by design** — streaming text before the validator has seen it would
let an unvalidated part number reach a user (FR-4). Frame boundaries are tested, not just payloads.

**The `structured` card union** (`services/orchestrator/.../cards.py`), built structurally from
tool results: `ProductCard` (ps, name, price, stock, image, url, difficulty, rating), `ComparisonCard`
(2–3 ProductCards, FR-11), `OrderCard` (status, timeline, items, tracking). `citations` (FR-19) and
`invalid_identifiers` (FR-4) ride on the message, pulled structurally — the frontend never parses
URLs/ids from prose. `current_model` is the **remembered appliance model** (FR-5), surfaced as a
session context chip.

## 4. Session & memory

A LangGraph Redis checkpointer (D11) keyed by `session_id` (24h TTL) persists `current_part`,
`current_model`, `order_*`, and the conversation summary across turns. The checkpointer requires
**Redis Stack** (RediSearch) and the **async** saver (the SSE path drives the graph with
`astream`). Two-turn pronoun resolution is proven across separate HTTP requests through the real
checkpointer.

## 5. The data pipeline

`pipeline/`. Ingestion is **discovery → SQS → fetchers → raw S3 → parsers → Aurora → embeddings →
OpenSearch**, with the moves that make it production-grade:

- **Fetch/parse separation (D12).** Fetchers write raw HTML to versioned S3
  (`raw/{page_type}/dt=YYYY-MM-DD/{sha256(url)}.html`) and never parse; parsers read **only** from
  S3. A parser bug is fixed by **re-parsing from S3 — zero re-crawl**. Demonstrated at volume: a
  214-page appliance-type drift was fixed with one parser change + a local re-parse, no request to
  the source site.
- **The drift contract.** Missing required fields raise a precise `SchemaDriftError(page_type,
  field, url)` instead of writing silent empty rows; failed pages keep their raw S3 object for
  re-parse. `KNOWN_EMPTY_SECTIONS` (Cover-Sheet schematic pages) skip the parts assertion without
  weakening detection for genuinely broken selectors (A12). Drift ran at **0.6% across 529 pages**,
  every one an honest decline (out-of-scope parts the contract refused to coerce).
- **Model-canonical compatibility (A9, resolved against real HTML).** Both part pages and model
  pages assert compatibility, but part pages are **paginated/incomplete per fetch** while model
  pages are **bounded/complete**. So pairs are ingested **only from model pages** (one
  `source_page_id` per pair); part pages contribute attributes only. This eliminates false-NO
  answers by construction — no schema change to 0001.
- **The staleness janitor.** Upsert + prune run in **one transaction** (so `now()` is the txn
  start: re-seen pairs survive, stale ones prune), and the prune is **scoped to the one section's
  `source_page_id`** — a failed/partial crawl can't mass-delete the compatibility catalog.
- **Content-hash change detection (NFR-7).** `sha256(body)` vs the stored hash skips unchanged
  pages (no re-parse, no re-embed); `search_sync` bookkeeping means the embedding job never
  re-embeds unchanged content.
- **Politeness by contract.** Discovery draws **only from the published sitemap** (cannot wander);
  a hard ~500-page cap with **per-category sub-budgets** (so high-volume part pages can't starve
  the compatibility-bearing section pages) that logs every drop; robots honored (with an explicit
  glob denylist over the stdlib parser's prefix-only gap, fail-safe to disallow); identified UA;
  token-bucket rate limit. Access uses the **real-Chrome Playwright channel** (the site is
  Akamai-403'd to headless) — access, not evasion; no proxies, no header spoofing.

The crawler self-healed a spot reclaim mid-run (430/529): the idempotent enqueue re-fetched only
the remaining 95 with zero duplication.

### Data model & accuracy primitives
- **`catalog.norm_id(raw)`** = `upper(regexp_replace(raw, '[^A-Za-z0-9]', '', ''))` — one
  format-tolerance, **mirrored in Python** (`entities.norm_id`) so extraction and DB lookup
  collapse identically. Stored generated `*_norm` columns keep lookups index-servable.
- **The four-verdict compatibility query** — `YES / NO / MODEL_NOT_FOUND / PART_NOT_FOUND` in one
  indexed round-trip, exactly one row. On `NO`, same-category best-stocked-first alternatives.
- **`symptom_vocab`** — the one human-judgment artifact: a curated map from source-attested
  part-page symptom phrasing to canonical symptoms, reviewed by the owner (near-but-wrong mappings
  refused). Repair ranking uses an honest signal (review count / in-stock) — per-part fix % don't
  exist at the source (A5 refuted by a fixture before any build).

## 6. Observability

D14, all proven live (Phase 4 — [WINS](WINS-LOG.md)). One process (gateway + embedded
orchestrator), one trace.

- **Traces (NFR-17).** OTel SDK; the OTLP exporter is **env-gated** (`OTEL_EXPORTER_OTLP_ENDPOINT`
  → Jaeger's native OTLP receiver — **no standalone Collector**, one fewer pod). A turn is
  `chat.turn` → explicit per-node `graph.*` child spans → `bedrock.converse` child spans carrying
  `gen_ai.request.model` + `gen_ai.usage.{input,output}_tokens`. Jaeger has **no public ingress**
  (no auth → port-forward only).
- **Metrics (NFR-18).** Prometheus scrapes the gateway `/metrics` via a ServiceMonitor:
  turns/latency/per-node-latency, guardrail blocks, invalid-id hits, feedback, and the **token +
  cost** counters (`lily_bedrock_tokens_total{model,direction}`, `lily_bedrock_cost_usd_total{model}`
  with a dated price table in `lily_common.metrics`). Four Grafana dashboards: Conversation health,
  Graph performance, Cost per conversation, Infra. Grafana is **login-only** (anonymous off,
  generated admin secret) on the shared ALB.
- **Logs (NFR-19).** Structured JSON via `lily_common.logging` (trace_id/session_id ContextVars).
  Fluent Bit ships **only the Lily app namespaces** (not kube-system, not observability itself —
  which self-ingested ~250k logs in a loop before the fix) to OpenSearch `lily-logs-*`, JSON merged
  to **root** so `trace_id` is a top-level field. The **log↔trace join** filters `lily-logs-*` by
  `trace_id` and matches the Jaeger `lily.trace_id` tag (the gateway UUID, not Jaeger's native id —
  by design).
- **Alerting (NFR-21).** Alertmanager → a Slack incoming webhook (Secrets Manager → ESO → mounted
  secret). A watchdog `PrometheusRule` proved delivery (`notifications_total{slack}=1`, `failed=0`).

Placement: the observability data plane runs on the **on-demand `system` pool**, not the single
reclaimable spot node that also runs the apps it watches.

## 7. Infrastructure

- **EKS namespaces** (D7): `frontend`, `agent`, `commerce`, `data`, `observability`, `platform`.
- **IaC layering** — `terraform/bootstrap` (state backend) · `envs/dev/infra` (VPC, EKS, ECR,
  Aurora, OpenSearch, S3/SQS, **IRSA roles**) · `envs/dev/platform` (ALB controller, cert-manager,
  external-secrets, **and the observability stack** — all `helm_release` with the hardening below).
  App workloads deploy via `make` (GitHub Actions only; no Argo CD — O4). No static credentials:
  **IRSA** for all AWS access, External Secrets for third-party secrets, no secret/account-id ever
  committed.
- **Platform hardening** (single-pass, 112 s) — every `helm_release` is
  `atomic + cleanup_on_fail + wait`; `depends_on` installs the ALB controller (whose mutating
  webhook intercepts all pod creation) before the rest; admission webhooks / cainjector /
  cert-controller are each **explicitly pinned to the on-demand `system` pool** (a spot reclaim of
  a webhook = cluster-wide admission failure). The kube-prometheus-stack operator + admission Jobs
  inherit the same pinning.
- **One shared ALB** via `group.name: lily-dev` (one ~$16.50/mo ALB, every host joins as a rule).
- **Cost guards (D17)** — spot pool for stateless apps, single NAT, Aurora **0-ACU autopause**,
  overnight `scale-down`. A held DB connection floors Aurora at 0.5 ACU while the gateway runs, so
  the autopause saving is realized through the nightly scale-down (gateway → 0 → connection closes
  → Aurora pauses) — discovered and decided live (A11 / D9 amendment).
- **Reliability** — `connect_with_retry` (full-jitter backoff sized to Aurora's 15–60s
  resume-from-pause; the single chokepoint so no service forgets it); forward-only idempotent
  migrations run **migrate-on-deploy**; the `lily_db` wheel force-includes the `.sql` files (a
  caught silent-no-op packaging bug).

## 8. Extensibility

- **New appliance categories** — the architecture is namespace-by-extension: the router taxonomy,
  the catalog schema, and the tools are appliance-agnostic; adding (say) washers is new crawl
  scope + seed data + a router-prompt line, not a re-architecture. The crawl is sitemap-driven and
  per-category-budgeted, so widening scope is a config change.
- **The embedded-orchestrator seam** — the orchestrator runs in the gateway process today, but
  `build_prod_graph()` injects `Deps` (conn, bedrock, search, guardrail) + the checkpointer and the
  tools are framework-agnostic Python, so splitting it into its own service is a **deploy/packaging
  change, not a refactor**.
- **A13 flat-list ingestion path** — model-canonical ingestion reaches only models with `/Sections/`
  pages; newer models expose a flat `/Models/{n}/Parts/` list. The documented extension is a second
  ingestion path parsing that list directly — which would revisit the A9 deny-glob and the per-page
  janitor (since flat-list pairs source from the parts page). Until then, "not covered" is the
  honest answer for flat-list-only models.
- **New channels** (voice, email) and **canary deploys** (Argo Rollouts — `k8s/` stays
  Argo-compatible) slot in without re-architecture; both are descoped-with-a-path, not designed out.

## 9. Where to look in the code

| Concern | Path |
|---|---|
| Graph wiring | `services/orchestrator/src/lily_orchestrator/graph.py` |
| Specialists + tools | `services/orchestrator/.../specialists.py`, `services/{catalog,orders,retrieval}/` |
| Guardrails / validator / entities | `services/orchestrator/.../{guardrails,validator,entities}.py` |
| SSE contract + cards | `services/gateway/.../chat.py`, `services/orchestrator/.../cards.py` |
| Crawl / parse / etl | `pipeline/{crawler,parsers,etl}/`, `libs/search/` |
| Schema | `db/migrations/` (norm_id, four-verdict tables, symptom_vocab, demo orders) |
| Infra / platform / observability | `terraform/envs/dev/{infra,platform}/`, `k8s/values/observability/` |
| Eval gate | `evals/{run,seed}.py`, `evals/cases.jsonl` |
