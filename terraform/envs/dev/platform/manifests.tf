# CRD instances via the kubectl provider — it tolerates CRDs that don't exist
# at plan time (kubernetes_manifest does not).

# Let's Encrypt issuer for internal/webhook certs. The public ALB uses ACM —
# this issuer is verified in Phase 0 and consumed from Phase 4 (ADR 0001).
resource "kubectl_manifest" "cluster_issuer" {
  yaml_body = yamlencode({
    apiVersion = "cert-manager.io/v1"
    kind       = "ClusterIssuer"
    metadata = {
      name = "letsencrypt-prod"
    }
    spec = {
      acme = {
        server = "https://acme-v02.api.letsencrypt.org/directory"
        email  = var.acme_email
        privateKeySecretRef = {
          name = "letsencrypt-prod-account-key"
        }
        solvers = [
          {
            dns01 = {
              route53 = {
                region       = var.region
                hostedZoneID = local.infra.zone_id
              }
            }
          }
        ]
      }
    }
  })

  depends_on = [helm_release.cert_manager]
}

# Proves ESO → Secrets Manager end-to-end. Secrets live under the lily/ prefix.
resource "kubectl_manifest" "cluster_secret_store" {
  yaml_body = yamlencode({
    apiVersion = "external-secrets.io/v1"
    kind       = "ClusterSecretStore"
    metadata = {
      name = "aws-secrets-manager"
    }
    spec = {
      provider = {
        aws = {
          service = "SecretsManager"
          region  = var.region
        }
      }
    }
  })

  depends_on = [helm_release.external_secrets]
}
