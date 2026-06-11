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
