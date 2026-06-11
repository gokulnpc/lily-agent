# Cluster-scoped / CRD-bearing platform components. Boundary rule: Terraform
# owns these; CI owns app workloads in k8s/ (see terraform/README.md).

resource "helm_release" "alb_controller" {
  # Failed installs roll back and clean up instead of stranding a broken release.
  atomic          = true
  cleanup_on_fail = true
  wait            = true
  timeout         = 600

  name       = "aws-load-balancer-controller"
  repository = "https://aws.github.io/eks-charts"
  chart      = "aws-load-balancer-controller"
  version    = var.alb_controller_chart_version
  namespace  = kubernetes_namespace.this["platform"].metadata[0].name

  set = [
    {
      name  = "clusterName"
      value = local.cluster_name
    },
    {
      name  = "vpcId"
      value = local.infra.vpc_id
    },
    {
      name  = "region"
      value = var.region
    },
    {
      name  = "serviceAccount.name"
      value = "aws-load-balancer-controller"
    },
    {
      name  = "serviceAccount.annotations.eks\\.amazonaws\\.com/role-arn"
      value = local.infra.irsa_alb_controller_role_arn
    },
    {
      name  = "nodeSelector.role"
      value = "system"
    },
  ]
}

resource "helm_release" "cert_manager" {
  # Failed installs roll back and clean up instead of stranding a broken release.
  atomic          = true
  cleanup_on_fail = true
  wait            = true
  timeout         = 600

  # The ALB controller's mutating webhook intercepts pod creation; installing
  # concurrently fails with "no endpoints available for service
  # aws-load-balancer-webhook-service". Order explicitly.
  depends_on = [helm_release.alb_controller]

  name       = "cert-manager"
  repository = "https://charts.jetstack.io"
  chart      = "cert-manager"
  version    = var.cert_manager_chart_version
  namespace  = kubernetes_namespace.this["platform"].metadata[0].name

  set = [
    {
      name  = "crds.enabled"
      value = "true"
    },
    {
      name  = "serviceAccount.name"
      value = "cert-manager"
    },
    {
      name  = "serviceAccount.annotations.eks\\.amazonaws\\.com/role-arn"
      value = local.infra.irsa_cert_manager_role_arn
    },
    {
      name  = "webhook.nodeSelector.role"
      value = "system"
    },
    {
      name  = "cainjector.nodeSelector.role"
      value = "system"
    },
    {
      # DNS-01 must resolve via public resolvers, not cluster DNS.
      name  = "dns01RecursiveNameserversOnly"
      value = "true"
    },
    {
      name  = "nodeSelector.role"
      value = "system"
    },
  ]
}

resource "helm_release" "external_secrets" {
  # Failed installs roll back and clean up instead of stranding a broken release.
  atomic          = true
  cleanup_on_fail = true
  wait            = true
  timeout         = 600

  depends_on = [helm_release.alb_controller]

  name       = "external-secrets"
  repository = "https://charts.external-secrets.io"
  chart      = "external-secrets"
  version    = var.external_secrets_chart_version
  namespace  = kubernetes_namespace.this["platform"].metadata[0].name

  set = [
    {
      name  = "installCRDs"
      value = "true"
    },
    {
      name  = "serviceAccount.name"
      value = "external-secrets"
    },
    {
      name  = "serviceAccount.annotations.eks\\.amazonaws\\.com/role-arn"
      value = local.infra.irsa_external_secrets_role_arn
    },
    {
      # The cert-controller only reports ready after provisioning the webhook
      # TLS secret; the chart default window (20s delay + 3x5s failures) is too
      # tight on first install and stalls `helm --wait`. Allow ~2 minutes.
      name  = "certController.readinessProbe.periodSeconds"
      value = "10"
    },
    {
      name  = "certController.readinessProbe.failureThreshold"
      value = "12"
    },
    {
      name  = "certController.nodeSelector.role"
      value = "system"
    },
    {
      name  = "webhook.nodeSelector.role"
      value = "system"
    },
    {
      name  = "nodeSelector.role"
      value = "system"
    },
  ]
}
