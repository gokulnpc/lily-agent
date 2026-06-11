# The six platform namespaces (D7). App charts deploy into these via CI/helm —
# Terraform only guarantees they exist.

resource "kubernetes_namespace" "this" {
  for_each = toset([
    "frontend",
    "agent",
    "commerce",
    "data",
    "observability",
    "platform",
  ])

  metadata {
    name = each.value

    labels = {
      "app.kubernetes.io/managed-by" = "terraform"
      "lily.dev/tier"                = each.value
    }
  }
}
