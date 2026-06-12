# Build from the repo root (uv workspace context):
#   docker build -f pipeline/crawler/Dockerfile -t lily-crawler .
FROM ghcr.io/astral-sh/uv:0.4.29 AS uv

FROM python:3.12-slim AS builder
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY libs/common libs/common
COPY db db
COPY pipeline/crawler pipeline/crawler
RUN uv sync --frozen --no-dev --no-editable --package lily-crawler

FROM python:3.12-slim
# The fetcher drives a real Chrome (headless is Akamai-403'd). Playwright's
# --with-deps pulls the OS libraries Chrome needs; the browser binary lands in
# /ms-playwright (PLAYWRIGHT_BROWSERS_PATH) so it's owned by root and readable
# by the app user.
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"
RUN playwright install --with-deps chrome
RUN groupadd --gid 10001 app && useradd --uid 10001 --gid app --create-home app
USER app
WORKDIR /app
# Entrypoint is set per workload by the k8s command:
#   python -m lily_crawler.runner discover
#   python -m lily_crawler.runner fetch-worker
CMD ["python", "-m", "lily_crawler.runner", "fetch-worker"]
