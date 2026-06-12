.PHONY: check fmt evals up down tf-fmt tf-validate deploy-gateway scale-down scale-up

# ---- Quality gates ---------------------------------------------------------

check: ## lint + typecheck + unit tests (all services)
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy libs services
	uv run pytest

fmt: ## auto-fix lint + formatting
	uv run ruff check --fix .
	uv run ruff format .

evals: ## golden-dataset evals (stub until Phase 2)
	@echo "no evals yet (Phase 2)"

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
# Injected at deploy time — the ARN embeds the account ID, never committed.
CERT_ARN ?= $(shell terraform -chdir=terraform/envs/dev/infra output -raw certificate_arn)

deploy-gateway: ## build, push to ECR, helm upgrade into the agent namespace
	aws ecr get-login-password --region $(AWS_REGION) | docker login --username AWS --password-stdin $(ECR_REGISTRY)
	docker build --platform linux/amd64 -f services/gateway/Dockerfile -t $(ECR_REGISTRY)/gateway:$(IMAGE_TAG) .
	docker push $(ECR_REGISTRY)/gateway:$(IMAGE_TAG)
	helm upgrade --install gateway k8s/charts/gateway \
		--namespace agent \
		--values k8s/values/agent/gateway.yaml \
		--set image.repository=$(ECR_REGISTRY)/gateway \
		--set image.tag=$(IMAGE_TAG) \
		--set ingress.certificateArn=$(CERT_ARN) \
		--wait --timeout 5m

# ---- Cost guards (D17) -------------------------------------------------------

scale-down: ## nodegroups to zero overnight; control plane/NAT/ALB keep billing
	./scripts/scale-down.sh

scale-up:
	./scripts/scale-up.sh
