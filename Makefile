.PHONY: check fmt evals migrate up down tf-fmt tf-validate deploy-gateway deploy-frontend scale-down scale-up frontend-check

# ---- Quality gates ---------------------------------------------------------

check: ## lint + typecheck + unit tests (all services)
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy libs services db pipeline
	uv run pytest

fmt: ## auto-fix lint + formatting
	uv run ruff check --fix .
	uv run ruff format .

frontend-check: ## frontend gate: tsc + eslint + vitest (Next.js app)
	cd frontend && pnpm install --frozen-lockfile && pnpm run check

evals: ## golden-dataset offline eval gate (NFR-23/24); needs compose Postgres
	uv run python -m evals.run

migrate: ## apply pending SQL migrations to the local compose Postgres
	uv run python -m lily_db.migrate

# ---- Local stack ------------------------------------------------------------

up: ## local compose profile: Postgres, OpenSearch, Redis, Jaeger, Prometheus, Grafana
	docker compose --profile core --profile obs up -d --wait

down:
	docker compose --profile core --profile obs down

# ---- Terraform --------------------------------------------------------------

TF_STACKS := terraform/bootstrap terraform/envs/dev/infra terraform/envs/dev/platform

tf-fmt:
	terraform fmt -recursive terraform/

tf-validate: ## fmt-check + init -backend=false + validate every stack
	terraform fmt -check -recursive terraform/
	@for stack in $(TF_STACKS); do \
		echo "== $$stack"; \
		terraform -chdir=$$stack init -backend=false -input=false >/dev/null && \
		terraform -chdir=$$stack validate || exit 1; \
	done

# ---- Deploy (dev only; announce before running — mutates AWS) ---------------

AWS_REGION ?= us-east-1
ECR_REGISTRY ?= $(shell aws sts get-caller-identity --query Account --output text).dkr.ecr.$(AWS_REGION).amazonaws.com
IMAGE_TAG ?= $(shell git rev-parse --short HEAD)
# Injected at deploy time — ARNs/endpoints embed the account ID, never committed.
TF_INFRA       = terraform -chdir=terraform/envs/dev/infra output -raw
CERT_ARN      ?= $(shell $(TF_INFRA) certificate_arn)
ORCH_ROLE_ARN ?= $(shell $(TF_INFRA) irsa_orchestrator_role_arn)
DB_SECRET_ARN ?= $(shell $(TF_INFRA) aurora_master_secret_arn)
DB_HOST       ?= $(shell $(TF_INFRA) aurora_endpoint)
OS_ENDPOINT   ?= $(shell $(TF_INFRA) opensearch_endpoint)
GUARDRAIL_ID  ?= $(shell $(TF_INFRA) guardrail_id)

deploy-redis: ## in-cluster Redis for the checkpointer (agent ns, dev)
	helm upgrade --install redis k8s/charts/redis --namespace agent --wait --timeout 2m

deploy-frontend: ## build, push to ECR, helm upgrade the Next.js chat UI into frontend
	aws ecr get-login-password --region $(AWS_REGION) | docker login --username AWS --password-stdin $(ECR_REGISTRY)
	docker build --platform linux/amd64 -f frontend/Dockerfile -t $(ECR_REGISTRY)/frontend:$(IMAGE_TAG) frontend
	docker push $(ECR_REGISTRY)/frontend:$(IMAGE_TAG)
	helm upgrade --install frontend k8s/charts/frontend \
		--namespace frontend \
		--values k8s/values/frontend/frontend.yaml \
		--set image.repository=$(ECR_REGISTRY)/frontend \
		--set image.tag=$(IMAGE_TAG) \
		--set ingress.certificateArn=$(CERT_ARN) \
		--wait --timeout 5m

deploy-gateway: ## build, push to ECR, helm upgrade the SSE gateway (+embedded orchestrator) into agent
	aws ecr get-login-password --region $(AWS_REGION) | docker login --username AWS --password-stdin $(ECR_REGISTRY)
	docker build --platform linux/amd64 -f services/gateway/Dockerfile -t $(ECR_REGISTRY)/gateway:$(IMAGE_TAG) .
	docker push $(ECR_REGISTRY)/gateway:$(IMAGE_TAG)
	helm upgrade --install gateway k8s/charts/gateway \
		--namespace agent \
		--values k8s/values/agent/gateway.yaml \
		--set image.repository=$(ECR_REGISTRY)/gateway \
		--set image.tag=$(IMAGE_TAG) \
		--set ingress.certificateArn=$(CERT_ARN) \
		--set serviceAccount.roleArn=$(ORCH_ROLE_ARN) \
		--set database.secretArn=$(DB_SECRET_ARN) \
		--set database.host=$(DB_HOST) \
		--set config.opensearchEndpoint=$(OS_ENDPOINT) \
		--set config.guardrailId=$(GUARDRAIL_ID) \
		--wait --timeout 5m

DB_SECRET_ARN ?= $(shell terraform -chdir=terraform/envs/dev/infra output -raw aurora_master_secret_arn)
DB_HOST       ?= $(shell terraform -chdir=terraform/envs/dev/infra output -raw aurora_endpoint)
RAW_BUCKET    ?= $(shell terraform -chdir=terraform/envs/dev/infra output -raw raw_bucket_name)
PARTS_BUDGET  ?= 80
CRAWL_MODE    ?= crawl   # `crawl` (enqueue + fetch, needs Chrome), `reparse` / `backfill` (no Chrome)

etl-image: ## build + push the etl image (Chrome-laden; needed only for CRAWL_MODE=crawl)
	aws ecr get-login-password --region $(AWS_REGION) | docker login --username AWS --password-stdin $(ECR_REGISTRY)
	docker build --platform linux/amd64 -f pipeline/etl/Dockerfile -t $(ECR_REGISTRY)/etl:$(IMAGE_TAG) .
	docker push $(ECR_REGISTRY)/etl:$(IMAGE_TAG)

crawl-enrich: ## run the etl Job in `data` against an EXISTING image (announce first). Build first with `make etl-image` only for CRAWL_MODE=crawl. CRAWL_MODE=crawl|reparse|backfill; PARTS_BUDGET=80/800
	helm upgrade --install etl-crawl k8s/charts/etl-crawl \
		--namespace data \
		--values k8s/values/data/etl-crawl.yaml \
		--set image.repository=$(ECR_REGISTRY)/etl \
		--set image.tag=$(IMAGE_TAG) \
		--set database.secretArn=$(DB_SECRET_ARN) \
		--set database.host=$(DB_HOST) \
		--set config.rawBucket=$(RAW_BUCKET) \
		--set crawl.mode=$(CRAWL_MODE) \
		--set crawl.partsBudget=$(PARTS_BUDGET)
	@echo "etl Job ($(CRAWL_MODE)) submitted to data ns on image tag $(IMAGE_TAG). Watch the newest Job:"
	@echo "  kubectl -n data get jobs -l app.kubernetes.io/name=etl-crawl"
	@echo "  kubectl -n data logs -f -l app.kubernetes.io/name=etl-crawl --tail=-1"

# ---- Cost guards (D17) -------------------------------------------------------

scale-down: ## nodegroups to zero overnight; control plane/NAT/ALB keep billing
	./scripts/scale-down.sh

scale-up:
	./scripts/scale-up.sh
