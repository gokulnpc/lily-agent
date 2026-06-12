# Bedrock Guardrail (D6) — the scope/PII/prompt-attack layer. Its id + version are
# surfaced as outputs and injected into the orchestrator as LILY_GUARDRAIL_ID /
# LILY_GUARDRAIL_VERSION at deploy (the app defaults to no-guardrail when unset,
# so offline/dev runs the Haiku scope gate alone).
#
# IAM: the orchestrator's IRSA role needs bedrock:ApplyGuardrail on this ARN plus
# bedrock:InvokeModel for the Haiku/Sonnet inference profiles — added with that
# role when the orchestrator service is deployed (no orchestrator role exists yet;
# the etl role only has Titan InvokeModel for embeddings).

module "guardrail" {
  source = "../../../modules/bedrock-guardrail"
  name   = "lily-dev-guardrail"
}
