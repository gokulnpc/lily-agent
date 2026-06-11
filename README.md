# Lily — PartSelect Chat Agent

Production-grade conversational agent for [PartSelect](https://www.partselect.com) refrigerator
and dishwasher parts: symptom diagnosis, part discovery, compatibility checks, installation
guidance, and order support. Built as a case study to real production standards on AWS
(EKS, Bedrock, Aurora, OpenSearch).

**Core principle: the LLM narrates, the database decides.** Every price, stock level,
compatibility verdict, and order fact comes from deterministic tool/SQL lookups — never
from model recall.

## Documentation

| Doc | Purpose |
|---|---|
| [docs/PRD.md](docs/PRD.md) | Product requirements |
| [docs/DECISIONS.md](docs/DECISIONS.md) | Locked architecture decisions + phase plan |
| [docs/adr/](docs/adr/) | Architecture decision records |
| [docs/runbooks/](docs/runbooks/) | Operational runbooks |
| [CLAUDE.md](CLAUDE.md) | Engineering rules and agent guardrails |

## Repo layout

```
terraform/        # all infra (bootstrap/, modules/, envs/dev/)
k8s/              # Helm charts per service + per-namespace values
services/         # gateway, orchestrator, retrieval, catalog, orders, notifications
pipeline/         # crawler, parsers, etl
libs/             # shared Python packages (lily-common)
frontend/         # Next.js app (Phase 3)
evals/            # golden dataset + eval runners (Phase 2/5)
local/            # configs for the local compose stack
scripts/          # operational scripts (scale-down/up)
```

## Quickstart

Prereqs: [uv](https://docs.astral.sh/uv/), Docker, Terraform ≥ 1.10, AWS CLI, helm, kubectl.

```sh
uv sync          # install the Python workspace
make check       # lint + typecheck + unit tests (all services)
make up          # local stack: Postgres, OpenSearch, Redis, Jaeger, Prometheus, Grafana
make down        # stop the local stack
```

Infra bring-up is documented in [docs/runbooks/phase0.md](docs/runbooks/phase0.md).
`terraform apply` is always a deliberate, human-confirmed action — never automated.

## Phase status

| Phase | Scope | Status |
|---|---|---|
| 0 | Foundations: monorepo, Terraform (VPC/EKS/ECR/IRSA), platform namespace, CI, compose | **in progress** |
| 1 | Data: Aurora schema, crawler/parsers, OpenSearch indexing | pending |
| 2 | Agent core: LangGraph, tools, guardrails, SSE gateway | pending |
| 3 | Frontend: Next.js chat UI | pending |
| 4 | Observability: dashboards, logs, alerts, Langfuse | pending |
| 5 | Quality: 100-case eval CI gate, semantic cache, canary | pending |
