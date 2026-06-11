# PRD — PartSelect Chat Agent ("Lily")

| | |
|---|---|
| **Status** | Draft v0.1 |
| **Author** | — |
| **Last updated** | June 11, 2026 |
| **Reviewers** | — |
| **Target release** | MVP in 4 phases (see Milestones) |

---

## 1. Overview

### 1.1 Problem statement
Customers shopping for refrigerator and dishwasher parts on PartSelect face three recurring points of friction: (1) identifying the correct part for a symptom ("my ice maker stopped working"), (2) verifying that a part fits their specific appliance model, and (3) understanding how to install the part once purchased. Today these tasks require navigating model lookup pages, compatibility tables, repair guides, and Q&A threads spread across the site. Customers who fail at any step either abandon the purchase, buy the wrong part (driving returns), or contact human support (driving cost).

### 1.2 Proposed solution
An embedded conversational agent on partselect.com that handles the full pre- and post-purchase journey for refrigerator and dishwasher parts: diagnosis, part discovery, compatibility verification, purchase assistance, installation guidance, and order support. The agent is strictly scoped to this domain and grounded in PartSelect's own catalog and content — every factual claim (price, stock, compatibility, fitment) comes from deterministic data lookups, never from model recall.

### 1.3 Goals
- **G1 — Accuracy:** Compatibility and product-fact answers are 100% consistent with the catalog database. Zero hallucinated part numbers reach users.
- **G2 — Resolution:** ≥70% of in-scope conversations reach a successful outcome (part identified, compatibility confirmed, install guidance delivered, or order question answered) without human handoff.
- **G3 — Conversion assist:** Agent conversations that identify a part end with an add-to-cart or product-page click-through ≥30% of the time.
- **G4 — Containment:** 100% of out-of-scope requests are deflected politely; 0 jailbreaks producing off-domain content in eval suite.
- **G5 — Performance:** First streamed token ≤2.0s p95; full deterministic answers (compatibility check) ≤4s p95.
- **G6 — Operability:** Every conversation is fully traced, metered, and replayable; cost per conversation is a first-class dashboard metric with budget alerts.

### 1.4 Non-goals
- Supporting appliance categories beyond refrigerators and dishwashers (architecture must allow adding them later, but MVP excludes them).
- Processing real payments inside the chat (cart handoff to PartSelect checkout only; order systems are mocked).
- General appliance advice unrelated to parts/repair (e.g., "which fridge should I buy?").
- Human live-chat replacement; the agent escalates via a handoff stub, it does not route to real agents in MVP.
- Mobile native apps (responsive web only).

### 1.5 Guiding principles
1. **LLM narrates, database decides.** Structured facts come from SQL/search tools; the model routes, reasons, and explains.
2. **Fail safe, not silent.** If a tool fails or data is missing, the agent says so and offers the relevant PartSelect page link — it never guesses.
3. **Everything observable.** No code ships without traces, metrics, and structured logs.
4. **Extensible by namespace.** New appliance categories, new tools, and new channels (voice, email) must slot in without re-architecture.

---

## 2. Users & personas

| Persona | Description | Primary jobs-to-be-done |
|---|---|---|
| **DIY repairer (primary)** | Homeowner with a broken appliance, moderate technical comfort, knows symptoms but not part names. | Diagnose symptom → find part → confirm fit → learn to install. |
| **Part-number shopper** | Knows the exact PS number or manufacturer number (from a technician, manual, or old part). | Look up part, verify fitment, check price/stock, buy. |
| **Post-purchase customer** | Already ordered; needs status, return, or installation help. | Track order, initiate return, get install steps/video. |
| **Property manager / pro** | Buys repeatedly across multiple appliance models. | Fast lookups, compatibility across a fleet of models, reorder. |

### Representative user stories
- *As a DIY repairer*, I can describe a symptom ("Whirlpool fridge ice maker not working") and receive a ranked diagnosis with the most likely parts, so that I can fix it without a technician.
- *As a part-number shopper*, I can ask "Is PS11752778 compatible with my WDT780SAEM1?" and get a definitive yes/no backed by the compatibility table, with alternatives if no.
- *As any user*, I can ask "How do I install part PS11752778?" and get step-by-step instructions, difficulty rating, required tools, and a video link.
- *As a post-purchase customer*, I can ask "Where is my order?" and get status by order number + email.
- *As a user who doesn't know my model number*, I can ask where to find it (per-brand sticker locations) or upload a photo of the model plate and have it read automatically.
- *As a returning user*, the agent remembers the appliance model I stated earlier in the session so I don't repeat it.

---

## 3. Functional requirements

Priority key: **P0** = MVP launch blocker · **P1** = fast-follow · **P2** = differentiator/backlog.

### 3.1 Conversation & scope
| ID | Requirement | Priority |
|---|---|---|
| FR-1 | Agent answers questions about refrigerator and dishwasher parts: discovery, details, pricing, stock, compatibility, installation, troubleshooting, orders. | P0 |
| FR-2 | Agent politely declines out-of-scope topics (other appliances, general chat, anything non-PartSelect) with a one-line redirect; never engages further. | P0 |
| FR-3 | Input guardrail (Bedrock Guardrails + Haiku classifier) screens scope and prompt-injection before orchestration; output guardrail validates topicality. | P0 |
| FR-4 | Deterministic post-validator: every part number (PS…) and model number in a response is checked against the catalog before rendering; failures trigger regeneration or graceful fallback. | P0 |
| FR-5 | Session memory: appliance model, brand, cart contents, and conversation summary persist across turns (Redis, 24h TTL); pronoun references ("this part") resolve correctly. | P0 |
| FR-6 | Multi-turn clarification: when a request is ambiguous (no model number for a compatibility ask), the agent asks one targeted question rather than guessing. | P0 |
| FR-7 | Streaming responses (SSE) with intermediate status events ("Checking compatibility…") emitted per agent-graph node. | P0 |
| FR-8 | Human-handoff stub: on repeated failure or explicit user request, agent offers escalation and captures a structured ticket (logged + SNS notification). | P1 |

### 3.2 Product discovery & details
| ID | Requirement | Priority |
|---|---|---|
| FR-9 | Lookup by PS number, manufacturer part number, or natural-language description (hybrid BM25 + vector search with rerank). | P0 |
| FR-10 | Product card rendering in chat: image, name, PS number, price, stock status, rating, install difficulty, link to product page, add-to-cart action. | P0 |
| FR-11 | Comparison: user can ask to compare 2–3 candidate parts; agent renders a comparison table (price, fit, reviews, difficulty). | P1 |
| FR-12 | Browsing aids: quick-reply chips for guided narrowing (brand → appliance → symptom). | P1 |

### 3.3 Compatibility
| ID | Requirement | Priority |
|---|---|---|
| FR-13 | `check_compatibility(part, model)` resolves exclusively via the part↔model compatibility table; answer is YES / NO / MODEL-NOT-FOUND, never inferred by the LLM. | P0 |
| FR-14 | On NO, agent proactively returns the correct equivalent part(s) for the stated model. | P0 |
| FR-15 | On MODEL-NOT-FOUND, agent offers model-number-location help (per-brand guidance). | P0 |
| FR-16 | Photo upload of model/serial plate → vision extraction of model number (Claude multimodal via Bedrock) → confirm with user before use. | P2 |

### 3.4 Troubleshooting & installation
| ID | Requirement | Priority |
|---|---|---|
| FR-17 | Symptom-based diagnosis: map symptom + brand/model to ranked likely-failed parts using repair-guide corpus (RAG) + catalog "fixes these symptoms" data. | P0 |
| FR-18 | Installation guidance per part: steps, difficulty, time estimate, tools, video link; cited to source page. | P0 |
| FR-19 | All RAG answers carry citations (link to the PartSelect page used). | P0 |
| FR-20 | Safety framing: instructions involving electrical/water connections include a standard disconnect-power/water caution. | P0 |

### 3.5 Orders & transactions (mocked backend)
| ID | Requirement | Priority |
|---|---|---|
| FR-21 | Order status lookup by order number + email against mock order service. | P0 |
| FR-22 | Return/cancellation initiation: agent collects required fields, creates a mock return record, confirms with reference ID. | P1 |
| FR-23 | In-chat cart: add/remove parts, view cart, hand off to PartSelect checkout via deep link. | P1 |
| FR-24 | Order-event notifications (mock shipped/delivered) via notification service (SNS → email/webhook). | P2 |

### 3.6 Feedback & learning loop
| ID | Requirement | Priority |
|---|---|---|
| FR-25 | Per-message 👍/👎 with optional comment; stored with trace ID for eval mining. | P0 |
| FR-26 | Thumbs-down conversations auto-surface in an admin review queue (Kibana saved search + weekly digest). | P1 |
| FR-27 | Admin dashboard: live conversation metrics, top intents, failure clusters, cost. | P2 |

---

## 4. Non-functional requirements

### 4.1 Performance & reliability
| ID | Requirement | Target |
|---|---|---|
| NFR-1 | Time to first streamed token | ≤2.0s p95 |
| NFR-2 | Deterministic tool answers (compatibility, order status) end-to-end | ≤4s p95 |
| NFR-3 | Full RAG answers end-to-end | ≤8s p95 |
| NFR-4 | Chat API availability | 99.5% monthly (MVP) |
| NFR-5 | Graceful degradation: Bedrock throttle/outage → retry w/ backoff → cross-region inference profile → static fallback message with search links | required |
| NFR-6 | Concurrent sessions supported at launch | 500 (HPA scales gateway/orchestrator) |

### 4.2 Cost
| ID | Requirement |
|---|---|
| NFR-7 | Cost per conversation computed from Bedrock token metadata, exported as Prometheus metric, visible in Grafana. |
| NFR-8 | Budget alert: hourly LLM spend > threshold → Alertmanager → Slack. |
| NFR-9 | Model tiering enforced: Haiku for guardrails/routing/rewrites; Sonnet only for specialist reasoning. Semantic cache (Redis, cosine ≥0.95, same intent+model context) short-circuits repeat questions. |
| NFR-10 | Infra cost guards: spot node groups for stateless workloads, Aurora Serverless v2 (0.5 ACU floor), single NAT gateway, overnight scale-down script for non-prod. |

### 4.3 Security & privacy
| ID | Requirement |
|---|---|
| NFR-11 | No static credentials: IRSA for all AWS access (Bedrock, S3, SQS, SNS); External Secrets Operator for third-party secrets. |
| NFR-12 | WAF on edge (rate limiting, common rule sets); per-session and per-IP rate limits at gateway (Redis token bucket). |
| NFR-13 | PII minimization: order lookups require order#+email pair; emails masked in logs/traces; Bedrock Guardrails PII filter on outputs. |
| NFR-14 | Prompt-injection defenses: input guardrail, tool-call allowlisting per agent, no raw user text interpolated into SQL (parameterized queries only). |
| NFR-15 | Network: private subnets for data plane; OpenSearch/Aurora/Redis not internet-accessible; TLS everywhere (cert-manager). |
| NFR-16 | Scraper compliance: respect robots.txt, identify user-agent, polite rate limits, raw data retained in private S3 only. |

### 4.4 Observability (launch-blocking, not optional)
| ID | Requirement |
|---|---|
| NFR-17 | Distributed tracing: OTel SDK in every service; one trace spans gateway → guardrail → router → tools → Bedrock call → response. Exported to Jaeger. trace_id returned in API response headers. |
| NFR-18 | Metrics: Prometheus scrape on all services. Mandatory series: request latency histograms per graph node, token usage & cost, tool error rates, guardrail trigger rate, cache hit rate, retrieval scores, scraper throughput/parse-failure rate. |
| NFR-19 | Logs: structured JSON via Fluent Bit → OpenSearch → Kibana; every log line carries trace_id, session_id, intent, graph_node. |
| NFR-20 | LLM-layer observability: Langfuse (self-hosted) capturing prompts, completions, evals, prompt versions; linked to Jaeger via trace_id. |
| NFR-21 | Alerting: Alertmanager routes → notification-service → SNS (Slack webhook + email). Required alerts: 5xx rate, Bedrock latency/throttle, eval-score regression, cost budget, scraper failures, certificate expiry, pod crash loops. |
| NFR-22 | Dashboards shipped with MVP: (1) Conversation health, (2) Agent graph performance, (3) Cost, (4) Ingestion pipeline, (5) Infra/K8s. |

### 4.5 Quality & evaluation
| ID | Requirement |
|---|---|
| NFR-23 | Golden eval set ≥100 cases: the 3 brief examples, per-intent coverage, adversarial out-of-scope, injection attempts, ambiguity cases. |
| NFR-24 | CI gate: every prompt/graph change runs evals; hard assertions (compatibility answers match SQL truth; zero invalid part numbers) must pass 100%; LLM-judge scores must not regress >2%. |
| NFR-25 | Canary deploys for orchestrator (Argo Rollouts or weighted service); auto-rollback on error-rate/eval-probe regression. |
| NFR-26 | Conversation replay: any production trace reproducible locally from LangGraph checkpoint + Langfuse record. |

---

## 5. System design summary

(Authoritative detail lives in the Architecture doc; summarized here for PRD completeness.)

- **Frontend:** Next.js (App Router), PartSelect branding, SSE streaming, rich message components (product cards, comparison tables, order cards, quick replies, citations, feedback).
- **Agent core:** LangGraph supervisor graph — input guardrail → intent router (Haiku) → specialist subgraphs (Product / Compatibility / Repair / Order, Sonnet) → deterministic validator → output guardrail. Redis checkpointer for state.
- **Tools (framework-agnostic Python):** search_parts, get_part_details, check_compatibility, find_models, diagnose_symptom (RAG), get_install_guide (RAG), get_order, initiate_return, cart ops.
- **Data:** Aurora PostgreSQL (parts, models, compatibility, guides, orders), OpenSearch (hybrid retrieval + log indices), ElastiCache Redis (sessions, semantic cache, rate limits), S3 (raw crawl, artifacts), SQS (crawl/index jobs).
- **Ingestion:** discovery crawler → SQS → fetchers (Playwright/HTTP) → raw S3 → parsers → normalizers → Aurora → embedding jobs (Titan v2) → OpenSearch. Content-hash change detection; nightly incremental.
- **Platform:** EKS namespaces — frontend, agent, commerce, data, observability, platform. Edge: Route53 → CloudFront → WAF → ALB. IaC: Terraform; CI/CD: GitHub Actions (+ Argo CD GitOps); images in ECR.
- **LLM:** Claude on Bedrock via Converse API; cross-region inference profiles; Titan embeddings.

---

## 6. Success metrics & instrumentation

| Metric | Definition | Target (90 days post-launch) | Source |
|---|---|---|---|
| Compatibility accuracy | Agent answer vs. truth table on sampled traffic + eval set | 100% | CI evals + audit job |
| Hallucinated part numbers | Invalid PS numbers reaching users | 0 | Post-validator metric |
| Resolution rate | In-scope convos reaching success state | ≥70% | Outcome classifier on traces |
| Scope containment | Out-of-scope deflection success | 100% on eval suite | Guardrail metrics + evals |
| TTFT / answer latency | p95 | ≤2.0s / ≤4–8s | Prometheus |
| Cost per conversation | Total Bedrock + infra amortized | <$0.06 median | Cost dashboard |
| Cache hit rate | Semantic cache | ≥20% after warmup | Redis metrics |
| CSAT proxy | 👍 / (👍+👎) | ≥85% | Feedback events |
| Add-to-cart assist | Convos w/ part identified → cart/product click | ≥30% | Frontend events |

---

## 7. Milestones

| Phase | Scope | Exit criteria |
|---|---|---|
| **0 — Foundations** | Monorepo, Terraform bootstrap (VPC, EKS, ECR, IRSA, state backend), platform namespace, CI skeleton | `terraform apply` from clean account; hello-world pod behind TLS ingress |
| **1 — Data** | Aurora schema, crawler/parser MVP on ~500 seed pages, S3/SQS plumbing, OpenSearch indexing | Compatibility query answerable via SQL; hybrid search returns relevant guides |
| **2 — Agent core** | LangGraph graph, tools, guardrails, Redis memory, FastAPI SSE gateway | All 3 brief examples + 20 eval cases pass via curl |
| **3 — Frontend** | Next.js chat, branding, streaming UI, product cards, feedback | E2E demo on real data |
| **4 — Observability** | OTel, Prometheus/Grafana (5 dashboards), Jaeger, Fluent Bit→Kibana, Alertmanager→SNS/Slack, Langfuse | Single trace visible end-to-end; test alert fires to Slack |
| **5 — Quality & polish** | 100-case eval suite in CI, semantic cache, full crawl widening, canary deploys, admin views, Loom prep | CI eval gate green; cost dashboard live; demo script rehearsed |

---

## 8. Risks & mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Source-site markup changes break parsers | High | Med | Parser/fetcher separation (re-parse from S3), schema-drift alerts, parser contract tests |
| Scraping blocked / rate-limited | Med | High | Polite crawl rates, backoff, incremental crawl, cached raw corpus in S3 keeps system functional |
| Bedrock quotas/throttling under load | Med | Med | Cross-region profiles, retry/backoff, semantic cache, Haiku offload |
| AWS cost overrun | Med | Med | NFR-10 guards, budget alerts, scale-to-zero script, destroy-safe Terraform |
| Hallucination despite grounding | Low | High | Deterministic validator (FR-4), hard CI assertions, citation requirement |
| Prompt injection via product content (scraped text in RAG) | Med | High | Treat retrieved content as data not instructions; output guardrail; injection eval cases |
| Compatibility data gaps (model not in table) | Med | Med | Explicit MODEL-NOT-FOUND path (FR-15), never infer fitment |
| Scope creep (it's a case study) | High | Med | Phase gates; P0-only for demo; backlog discipline |

---

## 9. Open questions

1. Crawl breadth for launch: all fridge+dishwasher brands, or top-N brands by catalog size first?
2. Auth story for order lookups in demo: seeded demo orders vs. free-form mock?
3. Langfuse self-hosted in-cluster vs. skipping in favor of Jaeger+custom — worth the extra pod footprint?
4. Do we want Argo CD in MVP or plain GitHub Actions deploys with Rollouts only?
5. Voice input (P2) — in scope for the Loom wow-factor or cut?

---

## 10. Appendix — canonical example dialogues

1. **Install:** "How can I install part number PS11752778?" → part card + steps + tools + video link + difficulty, cited.
2. **Compatibility:** "Is this part compatible with my WDT780SAEM1 model?" → resolves "this part" from session → SQL truth-table answer → alternative part if NO.
3. **Diagnosis:** "The ice maker on my Whirlpool fridge is not working. How can I fix it?" → asks for model if absent → ranked causes → likely parts as cards → install guidance offer.
4. **Out of scope:** "Can you recommend a good microwave?" → one-line polite decline + redirect to fridge/dishwasher parts.
5. **Order:** "Where's my order 38123, email jane@x.com?" → mock status card with timeline.
