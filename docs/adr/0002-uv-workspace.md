# ADR 0002 — Single uv workspace for all Python packages

**Status:** accepted · 2026-06-11

## Context

The monorepo will hold ~9 Python packages (6 services, 3 pipeline jobs) plus
shared libraries. CLAUDE.md mandates identical tooling everywhere: ruff, mypy
strict, pytest, Python 3.12.

## Decision

One **uv workspace** rooted at the repo root:

- Root `pyproject.toml` declares `[tool.uv.workspace]` members and depends on
  every member, so `uv sync` installs the whole workspace into one `.venv` with
  a single `uv.lock` — one resolution, no cross-service version skew.
- Shared `[tool.ruff]`, `[tool.mypy]` (strict) and `[tool.pytest.ini_options]`
  live in the root config only; services cannot drift.
- `libs/common` (`lily-common`) is consumed via `{ workspace = true }` sources.
- Dockerfiles run `uv sync --frozen --no-dev --no-editable --package <name>`
  from the repo-root build context: reproducible images, only the target
  service's dependency closure, workspace packages built (not editable) so the
  venv survives the multi-stage copy.
- Members are listed **explicitly** (not globbed): placeholder directories with
  only a README must not break `uv sync`. Each new service adds itself to
  `members` and the root dependencies when it gains code.

## Alternatives rejected

- **Independent per-service projects:** N lockfiles, N tool configs, guaranteed
  drift; cross-service refactors need path hacks.
- **Poetry/pip-tools monorepo:** no first-class workspace; slower CI installs.
