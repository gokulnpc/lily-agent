# Build from the repo root so the uv workspace (root pyproject + uv.lock + libs/) is in context:
#   docker build -f services/gateway/Dockerfile -t lily-gateway .
FROM ghcr.io/astral-sh/uv:0.4.29 AS uv

FROM python:3.12-slim AS builder
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY libs/common libs/common
COPY libs/search libs/search
COPY db db
# The orchestrator is embedded in the gateway (D4/D5 amended) — its tool libs
# build into the same venv.
COPY services/catalog services/catalog
COPY services/orders services/orders
COPY services/retrieval services/retrieval
COPY services/orchestrator services/orchestrator
COPY services/gateway services/gateway
# --no-editable: build workspace packages into the venv so it survives the copy
# to the runtime stage without the source tree.
RUN uv sync --frozen --no-dev --no-editable --package lily-gateway

FROM python:3.12-slim
RUN groupadd --gid 10001 app && useradd --uid 10001 --gid app --create-home app
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"
USER app
EXPOSE 8000
CMD ["uvicorn", "gateway.main:app", "--host", "0.0.0.0", "--port", "8000"]
