# ADR 0001 — Phase 0 edge scope: ACM on ALB now, CloudFront + WAF at Phase 3

**Status:** accepted · 2026-06-11

## Context

D8 locks the target edge topology: Route53 → CloudFront → WAF → ALB ingress.
The Phase 0 exit criterion, however, is only "hello-world pod behind TLS
ingress". The ALB terminates TLS with **ACM certificates exclusively** — it
cannot consume cert-manager/Let's Encrypt Kubernetes secrets.

## Decision

1. **Phase 0 edge is Route53 → ALB with an ACM certificate** (DNS-validated,
   issued in us-east-1 so the same cert serves CloudFront later). The ingress
   annotation `alb.ingress.kubernetes.io/certificate-arn` carries it; all Lily
   ingresses share one ALB via `group.name=lily-dev` (cost guard).
2. **CloudFront + WAF are deferred to Phase 3**, where caching behavior and WAF
   rules can be designed against the real frontend routes. D8 stays locked as
   the target topology — this ADR narrows Phase 0 scope only.
3. **cert-manager still ships in Phase 0** (locked platform scope): it provides
   internal/webhook TLS from Phase 4 (Langfuse, observability ingresses). Its
   Phase 0 verification is the `letsencrypt-prod` ClusterIssuer reaching
   `Ready=True` plus one throwaway Certificate issued and deleted.

## Consequences

- A real registered domain is a hard Phase 0 prerequisite (ACM DNS validation).
- external-dns is not installed; the one Route53 alias record to the shared ALB
  is created manually per the Phase 0 runbook, revisited in Phase 3.
