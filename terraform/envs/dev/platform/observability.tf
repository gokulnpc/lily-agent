# Phase 4 observability stack (D14). Platform-tier — same hardening as the ALB/
# cert-manager/ESO releases (atomic + cleanup_on_fail + wait + depends_on the ALB
# controller whose mutating webhook intercepts pod creation cluster-wide). Values
# live under k8s/values/observability/ (data, not Argo app charts — O4-compliant).

locals {
  obs_ns     = kubernetes_namespace.this["observability"].metadata[0].name
  obs_values = "${path.module}/../../../../k8s/values/observability"
  dashboards = "${local.obs_values}/dashboards"
}

# ---- Grafana admin credentials (generated; no extra Secrets Manager entry) ----
resource "random_password" "grafana_admin" {
  length  = 24
  special = false
}

resource "kubernetes_secret_v1" "grafana_admin" {
  metadata {
    name      = "lily-grafana-admin"
    namespace = local.obs_ns
  }
  data = {
    "admin-user"     = "admin"
    "admin-password" = random_password.grafana_admin.result
  }
}

# ---- Slack incoming-webhook URL: AWS Secrets Manager -> ESO -> k8s Secret ----
# Owner stages `lily/observability/slack-webhook` (a JSON {"url": "https://hooks.slack.com/..."})
# in Secrets Manager before apply. Alertmanager mounts the synced secret.
resource "kubectl_manifest" "slack_webhook" {
  yaml_body = yamlencode({
    apiVersion = "external-secrets.io/v1"
    kind       = "ExternalSecret"
    metadata = {
      name      = "lily-slack-webhook"
      namespace = local.obs_ns
    }
    spec = {
      refreshInterval = "1h"
      secretStoreRef  = { name = "aws-secrets-manager", kind = "ClusterSecretStore" }
      target          = { name = "lily-slack-webhook" }
      data = [
        {
          secretKey = "url"
          remoteRef = { key = "lily/observability/slack-webhook", property = "url" }
        }
      ]
    }
  })

  depends_on = [kubectl_manifest.cluster_secret_store]
}

# ---- kube-prometheus-stack (Prometheus + Grafana + Alertmanager) ----
resource "helm_release" "kube_prometheus_stack" {
  atomic          = true
  cleanup_on_fail = true
  wait            = true
  timeout         = 600

  # The operator ships an admission webhook (same class as the ALB webhook) —
  # serialize behind the ALB controller, and the slack/grafana secrets must exist
  # before Alertmanager/Grafana mount them.
  depends_on = [
    helm_release.alb_controller,
    helm_release.external_secrets,
    kubernetes_secret_v1.grafana_admin,
    kubectl_manifest.slack_webhook,
  ]

  name       = "kube-prometheus-stack"
  repository = "https://prometheus-community.github.io/helm-charts"
  chart      = "kube-prometheus-stack"
  version    = var.kube_prometheus_stack_chart_version
  namespace  = local.obs_ns

  values = [file("${local.obs_values}/kube-prometheus-stack.yaml")]

  # Account-bearing cert ARN injected here (never committed). The annotation key
  # carries dots, hence the escaping (same pattern as the SA role-arn annotations).
  set = [
    {
      name  = "grafana.ingress.annotations.alb\\.ingress\\.kubernetes\\.io/certificate-arn"
      value = local.infra.certificate_arn
    },
  ]
}

# ---- Jaeger all-in-one (in-memory; OTLP receiver for the gateway) ----
resource "helm_release" "jaeger" {
  atomic          = true
  cleanup_on_fail = true
  wait            = true
  timeout         = 600

  depends_on = [helm_release.alb_controller]

  name       = "jaeger"
  repository = "https://jaegertracing.github.io/helm-charts"
  chart      = "jaeger"
  version    = var.jaeger_chart_version
  namespace  = local.obs_ns

  values = [file("${local.obs_values}/jaeger.yaml")]
}

# ---- Fluent Bit DaemonSet -> OpenSearch (lily-logs-*) ----
resource "helm_release" "fluent_bit" {
  atomic          = true
  cleanup_on_fail = true
  wait            = true
  timeout         = 600

  depends_on = [helm_release.alb_controller]

  name       = "fluent-bit"
  repository = "https://fluent.github.io/helm-charts"
  chart      = "fluent-bit"
  version    = var.fluent_bit_chart_version
  namespace  = local.obs_ns

  values = [templatefile("${local.obs_values}/fluent-bit.yaml.tpl", {
    opensearch_host = local.infra.opensearch_endpoint
    role_arn        = local.infra.irsa_fluentbit_role_arn
  })]
}

# ---- Gateway /metrics scrape (ServiceMonitor CRD from kube-prometheus-stack) ----
resource "kubectl_manifest" "gateway_servicemonitor" {
  yaml_body = yamlencode({
    apiVersion = "monitoring.coreos.com/v1"
    kind       = "ServiceMonitor"
    metadata = {
      name      = "gateway"
      namespace = local.obs_ns
      labels    = { release = "kube-prometheus-stack" }
    }
    spec = {
      namespaceSelector = { matchNames = ["agent"] }
      selector          = { matchLabels = { "app.kubernetes.io/name" = "gateway" } }
      endpoints = [
        { port = "http", path = "/metrics", interval = "30s" }
      ]
    }
  })

  depends_on = [helm_release.kube_prometheus_stack]
}

# ---- Watchdog alert (proves Alertmanager -> Slack); always firing ----
resource "kubectl_manifest" "watchdog_rule" {
  yaml_body = yamlencode({
    apiVersion = "monitoring.coreos.com/v1"
    kind       = "PrometheusRule"
    metadata = {
      name      = "lily-watchdog"
      namespace = local.obs_ns
      labels    = { release = "kube-prometheus-stack" }
    }
    spec = {
      groups = [
        {
          name = "lily.watchdog"
          rules = [
            {
              alert       = "LilyObservabilityWatchdog"
              expr        = "vector(1)"
              for         = "0m"
              labels      = { severity = "info" }
              annotations = { summary = "Phase 4 alert pipeline is alive (watchdog)." }
            }
          ]
        }
      ]
    }
  })

  depends_on = [helm_release.kube_prometheus_stack]
}

# ---- Grafana dashboards (sidecar loads labelled ConfigMaps) ----
resource "kubernetes_config_map_v1" "dashboards" {
  metadata {
    name      = "lily-dashboards"
    namespace = local.obs_ns
    labels    = { grafana_dashboard = "1" }
  }
  data = {
    "conversation-health.json" = file("${local.dashboards}/conversation-health.json")
    "graph-performance.json"   = file("${local.dashboards}/graph-performance.json")
    "cost.json"                = file("${local.dashboards}/cost.json")
    "infra.json"               = file("${local.dashboards}/infra.json")
  }

  depends_on = [helm_release.kube_prometheus_stack]
}
