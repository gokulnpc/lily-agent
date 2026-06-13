# evals

Golden-dataset eval suite (NFR-23/24). Two tiers:

## Offline tier — the CI gate (`make evals`)
`run.py` runs every `tier: offline` case in `cases.jsonl` through the **real agent
graph** with `FakeConverse` (canned router/guardrail decisions) + compose Postgres
(real tools, real validator, real compatibility SQL). `seed.py` is a deterministic
fixture catalog so verdicts are a known truth table. The seed is **uncommitted**
(shared connection, rolled back at the end) so the gate leaves zero DB residue and
never collides with the unit-test fixtures.

Hard, all-or-nothing assertions (any failure exits non-zero):
- compatibility verdicts match the SQL truth table (`check_compatibility`),
- `invalid_identifiers == []` on every answered case (FR-4),
- `blocked == true` on every out-of-scope/injection case, with **no** specialist run,
- `citations` present on every answer that should cite (FR-19),
- correct `primary_intent` / specialist ran.

Runs in CI (`.github/workflows/ci.yml`, with a Postgres service) and locally via
`make evals` (needs `make up`; skips cleanly with no DB).

**Findings, not knobs:** a failing case is a finding — fix the agent or the
expectation deliberately; never tune a case to mask a real regression.

## Live smoke tier (on demand, NOT CI-blocking)
A `tier: live` subset (e.g. retrieval-backed diagnosis, content-borne injection
resistance) runs against the **deployed gateway** with the same assertions plus
latency capture (p50/p95 vs the NFR targets, reported not gated). The offline tier
can't exercise OpenSearch retrieval or a real LLM's injection resistance — those
live here.

## What the offline tier deliberately does NOT cover
The LLM's actual routing/narration quality (router intents are canned), OpenSearch
retrieval (no `os_client` offline), and real prompt-injection resistance
(FakeConverse can't be injected) — all live-tier concerns.
