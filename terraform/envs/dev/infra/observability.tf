# IRSA for the Fluent Bit log shipper (observability namespace). It writes
# container logs to the SHARED OpenSearch domain (D10), into the LOG index
# namespace `lily-logs-*` — kept separate from the retrieval indices
# `retrieval-*` (NFR-19). Mirrors irsa_orchestrator.
#
# Index isolation on an IAM-auth (no FGAC) domain is asymmetric:
#   - READS are path-scoped (`/<index>/_search`) → enforceable by IAM. The
#     serve-time orchestrator role is scoped to `retrieval-*` (orchestrator.tf),
#     so it can NOT read the log indices.
#   - BULK WRITES go to the domain-root `/_bulk` endpoint, so IAM can't pin them
#     to an index by path. We grant POST on `/_bulk` plus management of
#     `lily-logs-*`; the bulk body still names the index (Fluent Bit config only
#     ever writes `lily-logs-*`). True body-level isolation would require FGAC
#     (a domain change, out of scope). This is the honest dev posture.

module "irsa_fluentbit" {
  source = "../../../modules/irsa"

  role_name            = "lily-dev-fluentbit"
  oidc_provider_arn    = module.eks.oidc_provider_arn
  oidc_provider_url    = module.eks.oidc_provider_url
  namespace            = "observability"
  service_account      = "fluent-bit"
  create_inline_policy = true
  policy_json          = data.aws_iam_policy_document.fluentbit.json
}

data "aws_iam_policy_document" "fluentbit" {
  statement {
    sid       = "OpenSearchBulkWrite"
    actions   = ["es:ESHttpPost"]
    resources = ["arn:aws:es:${var.region}:${data.aws_caller_identity.current.account_id}:domain/lily-dev/_bulk"]
  }

  statement {
    sid     = "OpenSearchLogIndexManage"
    actions = ["es:ESHttpPut", "es:ESHttpPost", "es:ESHttpHead", "es:ESHttpGet"]
    # LOG namespace only — Fluent Bit can create/probe lily-logs-* indices and
    # templates, but has no read/search on retrieval-*.
    resources = ["arn:aws:es:${var.region}:${data.aws_caller_identity.current.account_id}:domain/lily-dev/lily-logs*"]
  }
}

output "irsa_fluentbit_role_arn" {
  description = "IRSA role for the Fluent Bit DaemonSet — set as the fluent-bit SA roleArn"
  value       = module.irsa_fluentbit.role_arn
}
