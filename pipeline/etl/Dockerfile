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
COPY pipeline/etl pipeline/etl
RUN uv sync --frozen --no-dev --no-editable --package lily-etl

FROM python:3.12-slim
RUN groupadd --gid 10001 app && useradd --uid 10001 --gid app --create-home app
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"
USER app
CMD ["python", "-m", "lily_etl.runner"]
