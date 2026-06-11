# Runbook — Phase 0 bring-up

End-to-end procedure from a clean AWS account to the exit criteria:
`terraform apply` clean · hello-world (gateway) pod behind TLS ingress · `make check` green.

> Every `terraform apply`/`destroy`, ECR push, and `helm upgrade` requires
> explicit owner confirmation in-session (CLAUDE.md hard stop).

## Prerequisites

- AWS account + an IAM principal with admin-capable permissions (the current
  `nfl-gokul` user could not call EKS APIs when tested — verify before starting).
- Terraform ≥ 1.10, helm, kubectl, AWS CLI v2, Docker, uv.
- **A registered domain.** Register one in Route53 (~$13/yr). Registration
  auto-creates a hosted zone — we let Terraform manage its own zone instead
  (step 3).

## 1. Bootstrap the state bucket (once)

```sh
cd terraform/bootstrap
terraform init && terraform apply
terraform output state_bucket_name
```

Then wire the bucket name in:
- `terraform/envs/dev/infra/backend.tf` and `terraform/envs/dev/platform/backend.tf`
  (replace `lily-tfstate-REPLACE_AFTER_BOOTSTRAP`)
- both stacks' `dev.auto.tfvars` (`state_bucket_name`)
- `terraform/bootstrap/README.md` (record it)

## 2. Configure variables

```sh
cd terraform/envs/dev/infra
cp dev.auto.tfvars.example dev.auto.tfvars   # gitignored
# set: domain_name, admin_principal_arn, public_access_cidrs (your IP/32),
#      github_repository, state_bucket_name
cd ../platform
cp dev.auto.tfvars.example dev.auto.tfvars   # set: state_bucket_name, acme_email
```

Verify the pinned EKS version is still in standard support; bump
`cluster_version` if not.

## 3. Apply infra (~15–20 min)

```sh
cd terraform/envs/dev/infra
terraform init && terraform apply
```

**Immediately after:** point the registered domain at the Terraform-managed zone —
Route53 console → Registered domains → your domain → replace name servers with
`terraform output zone_name_servers`. ACM validation (and the apply's
`aws_acm_certificate_validation`) completes only after NS propagation; if the
apply times out waiting, fix NS and re-apply.

Optionally delete the registrar's auto-created hosted zone (it costs $0.50/mo
and is unused).

## 4. Apply platform

```sh
aws eks update-kubeconfig --name lily-dev --region us-east-1
cd terraform/envs/dev/platform
terraform init && terraform apply
```

Verify:

```sh
kubectl get pods -n platform        # alb-controller, cert-manager, external-secrets Running
kubectl get clusterissuer           # letsencrypt-prod Ready=True
kubectl get clustersecretstore      # aws-secrets-manager Ready=True
```

cert-manager end-to-end check (throwaway cert, then delete):

```sh
kubectl -n platform apply -f - <<'EOF'
apiVersion: cert-manager.io/v1
kind: Certificate
metadata: {name: smoke-test}
spec:
  secretName: smoke-test-tls
  dnsNames: ["smoke.dev.<your-domain>"]
  issuerRef: {name: letsencrypt-prod, kind: ClusterIssuer}
EOF
kubectl -n platform wait certificate/smoke-test --for=condition=Ready --timeout=5m
kubectl -n platform delete certificate smoke-test secret smoke-test-tls
```

## 5. Deploy the gateway

Fill `k8s/values/agent/gateway.yaml`: `ingress.host` (`gateway.dev.<domain>`)
and `ingress.certificateArn` (`terraform -chdir=terraform/envs/dev/infra output -raw certificate_arn`). Then:

```sh
make deploy-gateway    # ECR login → build → push → helm upgrade
```

Create the DNS record (manual until external-dns in Phase 3): Route53 console →
the Terraform zone → create record `gateway.dev.<domain>`, type A, **Alias** to
the ALB the controller created (Alias to Application Load Balancer → us-east-1 →
the `lily-dev` group ALB).

## 6. Verify exit criteria

```sh
kubectl -n agent get pods -o wide        # Running, on a role=stateless node
curl -sS https://gateway.dev.<domain>/healthz   # {"status":"ok"}, valid cert
curl -sSI http://gateway.dev.<domain>/healthz   # 301 → https
make check                                # green
terraform -chdir=terraform/envs/dev/infra plan     # no diff
terraform -chdir=terraform/envs/dev/platform plan  # no diff
```

## 7. CI secrets/variables (GitHub repo settings)

| Kind | Name | Value |
|---|---|---|
| Secret | `AWS_PLAN_ROLE_ARN` | `terraform output -raw ci_plan_role_arn` |
| Secret | `TF_ADMIN_PRINCIPAL_ARN` | the admin principal ARN |
| Variable | `TF_DOMAIN_NAME` | the domain |
| Variable | `TF_PUBLIC_ACCESS_CIDRS` | `["<your-ip>/32"]` |
| Variable | `TF_STATE_BUCKET_NAME` | the state bucket |

First infra apply happens locally before the OIDC role exists, so the CI plan
job goes green from the second PR onward.

## Cost guards (D17)

~$195/mo while running (EKS $73, NAT $32, nodes ~$70, ALB ~$17).

- Overnight: `make scale-down` (nodes → 0; ~$125/mo still bills).
- Idle > 2 days: `terraform destroy` platform, then infra (state bucket and
  domain survive; rebuild ≈ 25–30 min). Destroy platform **first** — it owns
  the ALB; destroying infra first orphans it.
- Consider an AWS Budgets alert at $100/mo (console, 2 min).
