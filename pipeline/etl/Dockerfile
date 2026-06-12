# Build from the repo root (uv workspace context):
#   docker build -f pipeline/etl/Dockerfile -t lily-etl .
FROM ghcr.io/astral-sh/uv:0.4.29 AS uv

FROM python:3.12-slim AS builder
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY libs/common libs/common
COPY libs/search libs/search
COPY db db
COPY pipeline/parsers pipeline/parsers
COPY pipeline/crawler pipeline/crawler
COPY pipeline/etl pipeline/etl
RUN uv sync --frozen --no-dev --no-editable --package lily-etl

FROM python:3.12-slim
# The seed-crawl orchestrator drives Chrome (headless is Akamai-403'd), so the
# image ships the real Chrome binary — same as the crawler image.
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"
RUN playwright install --with-deps chrome
# xvfb provides a virtual display so headed Chrome runs in a pod (headless is
# Akamai-403'd, D12). Invoke via `xvfb-run -a python -m ...`. xauth is required by
# xvfb-run itself (it errors "xauth command not found" without it).
RUN apt-get update && apt-get install -y --no-install-recommends xvfb xauth && rm -rf /var/lib/apt/lists/*
RUN groupadd --gid 10001 app && useradd --uid 10001 --gid app --create-home app
USER app
WORKDIR /app
CMD ["python", "-m", "lily_etl.runner"]
