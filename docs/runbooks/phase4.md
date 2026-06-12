# Runbook — Phase 4 observability bring-up

Deploy order and the four exit proofs. **4c is gated** (touches IAM + the
OpenSearch access policy + ALB/Route53). All commands use `AWS_PROFILE=partselect-dev`.

## Prerequisites (before the gated apply)

1. **Slack incoming-webhook** staged in Secrets Manager (owner action):
   ```
   aws secretsmanager create-secret --name lily/observability/slack-webhook \
     --secret-string '{"url":"https://hooks.slack.com/services/XXX/YYY/ZZZ"}'
   ```
   ESO syncs it to the `lily-slack-webhook` k8s Secret; Alertmanager mounts it.
2. Cluster up (the D17 scale-down may have it at zero — `make scale-up` first).

## Apply order (4c)

1. **infra** (adds `irsa_fluentbit` + the OpenSearch principal, and tightens the
   orchestrator OpenSearch scope to `retrieval-*`):
   ```
   terraform -chdir=terraform/envs/dev/infra apply
   ```
   ⚠ This re-scopes the live gateway's OpenSearch IAM from `domain/*` to
   `retrieval-*`. After apply, smoke-test retrieval (the ice-maker example) to
   confirm `diagnose_symptom`/`search_parts` still work.
2. **platform** (the 3 helm releases + ESO secret + watchdog rule + ServiceMonitor
   + dashboards):
   ```
   terraform -chdir=terraform/envs/dev/platform apply
   ```
3. **Grafana DNS** — `grafana.dev.lily-agent.com` A-alias to the shared ALB
   (mirror gateway.dev; the wildcard cert already covers it):
   ```
   aws route53 change-resource-record-sets --hosted-zone-id Z03433702JD3UKK1GTRIZ \
     --change-batch '{"Changes":[{"Action":"UPSERT","ResourceRecordSet":{
       "Name":"grafana.dev.lily-agent.com.","Type":"A","AliasTarget":{
       "HostedZoneId":"Z35SXDOTRQ7X7K",
       "DNSName":"<shared-alb-dns>.us-east-1.elb.amazonaws.com.",
       "EvaluateTargetHealth":true}}}]}'
   ```
4. **Gateway redeploy** to export OTLP (the env now lives in
   `k8s/values/agent/gateway.yaml`): `make deploy-gateway` (verify the running
   digest — task #63 caveat; use a distinct tag).

## The four proofs (exit criteria)

1. **End-to-end Jaeger trace.** Send one chat turn, then port-forward Jaeger
   (no public ingress — it has no auth):
   ```
   kubectl -n observability port-forward svc/jaeger-query 16686:16686
   ```
   Open http://localhost:16686 → service `gateway` → one `chat.turn` with child
   spans `graph.input_guardrail/router/specialist/validator/output_guardrail` and
   `bedrock.converse` (model id + `gen_ai.usage.*` tokens), with timings.
2. **Grafana dashboards** at https://grafana.dev.lily-agent.com (login: `admin` /
   `kubectl -n observability get secret lily-grafana-admin -o jsonpath='{.data.admin-password}' | base64 -d`).
   Drive proof traffic, then confirm the 4 dashboards: Conversation health, Graph
   performance, Cost per conversation, Infra.
3. **Log↔trace join.** In OpenSearch Dashboards, index pattern `lily-logs-*`,
   filter `trace_id: "<id>"` for a turn → paste the same id into Jaeger's
   `lily.trace_id` tag search. (Join is by the UUID tag, not Jaeger's native
   traceID — by design.)
4. **Alert to Slack.** The `lily-watchdog` rule (`vector(1)`) fires on install →
   Alertmanager → the Slack channel. Show the message. (Silence it afterward.)

## Notes

- **Jaeger has no ingress** (no auth) — port-forward only; never on the public ALB.
- **Grafana** is on the public ALB but login-only (anonymous disabled, admin
  password from the generated `lily-grafana-admin` secret). Optional extra gate:
  uncomment `inbound-cidrs` in the kps values to restrict source IPs.
- **Teardown:** `terraform -chdir=terraform/envs/dev/platform destroy` removes the
  releases; in-memory Jaeger traces + ≤6h Prometheus data are disposable.
