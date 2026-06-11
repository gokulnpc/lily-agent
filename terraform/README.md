# terraform/ — all infrastructure

## Stacks

| Stack | State | Purpose |
|---|---|---|
| `bootstrap/` | **local** (gitignored) | One-time: S3 bucket for everyone else's remote state |
| `envs/dev/infra/` | `s3: dev/infra.tfstate` | AWS resources: VPC, EKS, ECR, IRSA roles, DNS/ACM, GitHub OIDC |
| `envs/dev/platform/` | `s3: dev/platform.tfstate` | In-cluster platform: namespaces, ALB controller, cert-manager, external-secrets |

Apply order: bootstrap (once) → infra → platform. The platform stack reads infra
outputs via `terraform_remote_state`; its Kubernetes/Helm providers use EKS exec
auth — deliberately a separate stack from the one that creates the cluster.

State locking is S3-native (`use_lockfile = true`, Terraform ≥ 1.10). No DynamoDB.

## Ownership boundary

**Terraform owns the cluster and everything cluster-scoped or CRD-bearing**
(namespaces, controllers, issuers, secret stores). **CI/helm owns app workloads**
in `k8s/` (deployments, services, app ingresses). This keeps `k8s/` pure app
charts — compatible with Argo CD if O4 is ever revisited.

## Modules

| Module | Contents |
|---|---|
| `network` | VPC (10.40.0.0/16), 2 AZs, public+private subnets, single NAT (D17), S3 gateway endpoint, ALB discovery tags |
| `eks` | Cluster (API auth mode, access entries), OIDC provider, system (on-demand) + stateless-spot node groups, addons (vpc-cni, kube-proxy, coredns, metrics-server) |
| `ecr` | Repositories with scan-on-push and keep-last-10 lifecycle |
| `irsa` | Generic role trusted by one namespace/service-account pair |
| `dns` | Public hosted zone + ACM cert (apex, `*.domain`, `*.dev.domain`) |
| `github-oidc` | GitHub Actions OIDC provider + read-only `lily-ci-plan` role |

The `aws-ebs-csi-driver` addon lives in `envs/dev/infra/main.tf` (not the eks
module) because its IRSA role references the cluster's OIDC provider — keeping
it in the module would cycle module references.

## Conventions

- Every module: `main.tf`, `variables.tf`, `outputs.tf`, `versions.tf`. No
  `provider` blocks inside modules.
- All variables typed + described. Outputs named after the thing (`vpc_id`,
  `certificate_arn`).
- Tags via provider `default_tags`: `Project=lily`, `Env=dev`, `ManagedBy=terraform`.
- Terraform ≥ 1.10, AWS provider ~> 6.0, pinned in each `versions.tf`.
- `dev.auto.tfvars` is gitignored (it contains the account-ID-bearing principal
  ARN and your IP); copy from `dev.auto.tfvars.example`.
- **`terraform apply` / `destroy` require explicit owner confirmation — never
  run in CI** (CLAUDE.md hard stop).

## Reserved future modules (do not create early)

| Module | Phase | Contract sketch |
|---|---|---|
| `aurora` | 1 | Aurora PostgreSQL Serverless v2, 0.5 ACU floor (D9); consumes `vpc_id` + `private_subnet_ids`, creates own SG |
| `opensearch` | 1 | Single domain, retrieval + log index namespaces (D10); private subnets |
| `s3-sqs` | 1 | Raw-crawl bucket (versioned), crawl/index queues (D12) |
| `redis` | 2 | ElastiCache: sessions, semantic cache, rate limits (D11) |
