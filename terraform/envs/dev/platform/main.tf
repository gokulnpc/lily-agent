# Cluster-scoped / CRD-bearing platform components. Boundary rule: Terraform
# owns these; CI owns app workloads in k8s/ (see terraform/README.md).

resource "helm_release" "alb_controller" {
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
      name  = "nodeSelector.role"
      value = "system"
    },
  ]
}
