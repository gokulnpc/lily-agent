# IRSA for the gateway/orchestrator pod (agent namespace). The orchestrator is
# embedded in the gateway process (D4/D5 amended), so it uses the gateway SA.
# Needs: Bedrock InvokeModel (Haiku/Sonnet specialists + Titan embeddings) +
# ApplyGuardrail (D6), and OpenSearch query access (diagnose_symptom/search_parts).
# It does NOT need Secrets Manager: the Aurora DB URL arrives via an ESO-synced
# k8s Secret (same ClusterSecretStore the data namespace uses).

module "irsa_orchestrator" {
  source = "../../../modules/irsa"

  role_name            = "lily-dev-orchestrator"
  oidc_provider_arn    = module.eks.oidc_provider_arn
  oidc_provider_url    = module.eks.oidc_provider_url
  namespace            = "agent"
  service_account      = "gateway"
  create_inline_policy = true
  policy_json          = data.aws_iam_policy_document.orchestrator.json
}

data "aws_iam_policy_document" "orchestrator" {
  statement {
    sid     = "BedrockInvoke"
    actions = ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"]
    # Claude (router/specialists) + Titan (retrieval embeddings), via the
    # cross-region inference profiles (NFR-5) and the underlying foundation models.
    resources = [
      "arn:aws:bedrock:*::foundation-model/anthropic.claude-*",
      "arn:aws:bedrock:*::foundation-model/amazon.titan-embed-text-v2:0",
      "arn:aws:bedrock:*:${data.aws_caller_identity.current.account_id}:inference-profile/*",
    ]
  }

  statement {
    sid       = "BedrockGuardrail"
    actions   = ["bedrock:ApplyGuardrail"]
    resources = [module.guardrail.guardrail_arn]
  }

  statement {
    sid     = "OpenSearchQuery"
    actions = ["es:ESHttpGet", "es:ESHttpPost", "es:ESHttpHead"]
    # Constructed ARN (not module.opensearch.arn) to avoid a dependency cycle —
    # the domain's access policy references this role (see data-plane.tf).
    # Scoped to the RETRIEVAL index namespace (retrieval-parts / retrieval-symptoms
    # / retrieval-guides — lily_search.index.RETRIEVAL_PREFIX). Phase 4 put the log
    # indices (lily-logs-*) on the SAME domain (D10); pinning the serve-time role to
    # retrieval-* means it can NOT read the logs (reads are path-scoped, so IAM
    # enforces this). Bulk/_search to retrieval-* is covered by the prefix.
    resources = [
      "arn:aws:es:${var.region}:${data.aws_caller_identity.current.account_id}:domain/lily-dev/retrieval-*",
    ]
  }
}

output "irsa_orchestrator_role_arn" {
  description = "IRSA role for the gateway/orchestrator pod — set as the gateway SA roleArn"
  value       = module.irsa_orchestrator.role_arn
}
