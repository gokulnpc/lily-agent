locals {
  cluster_name = "lily-dev"
}

module "network" {
  source = "../../../modules/network"

  name         = "lily-dev"
  cluster_name = local.cluster_name
}

module "ecr" {
  source = "../../../modules/ecr"

  # Extend as services gain images: orchestrator, retrieval, catalog, orders,
  # notifications, frontend.
  repository_names = ["gateway"]
}

module "dns" {
  source = "../../../modules/dns"

  domain_name = var.domain_name
}

module "github_oidc" {
  source = "../../../modules/github-oidc"

  github_repository = var.github_repository
  state_bucket_name = var.state_bucket_name
}

module "eks" {
  source = "../../../modules/eks"

  cluster_name        = local.cluster_name
  cluster_version     = var.cluster_version
  private_subnet_ids  = module.network.private_subnet_ids
  public_access_cidrs = var.public_access_cidrs
  admin_principal_arn = var.admin_principal_arn
}

# ---- IRSA roles for platform controllers ------------------------------------

data "aws_caller_identity" "current" {}

module "irsa_alb_controller" {
  source = "../../../modules/irsa"

  role_name            = "lily-dev-alb-controller"
  oidc_provider_arn    = module.eks.oidc_provider_arn
  oidc_provider_url    = module.eks.oidc_provider_url
  namespace            = "platform"
  service_account      = "aws-load-balancer-controller"
  create_inline_policy = true
  policy_json          = file("${path.module}/policies/aws-load-balancer-controller.json")
}

data "aws_iam_policy_document" "cert_manager" {
  statement {
    actions   = ["route53:GetChange"]
    resources = ["arn:aws:route53:::change/*"]
  }

  statement {
    actions = [
      "route53:ChangeResourceRecordSets",
      "route53:ListResourceRecordSets",
    ]
    resources = ["arn:aws:route53:::hostedzone/${module.dns.zone_id}"]
  }

  statement {
    actions   = ["route53:ListHostedZonesByName"]
    resources = ["*"]
  }
}

module "irsa_cert_manager" {
  source = "../../../modules/irsa"

  role_name            = "lily-dev-cert-manager"
  oidc_provider_arn    = module.eks.oidc_provider_arn
  oidc_provider_url    = module.eks.oidc_provider_url
  namespace            = "platform"
  service_account      = "cert-manager"
  create_inline_policy = true
  policy_json          = data.aws_iam_policy_document.cert_manager.json
}

data "aws_iam_policy_document" "external_secrets" {
  statement {
    actions = [
      "secretsmanager:GetSecretValue",
      "secretsmanager:DescribeSecret",
      "secretsmanager:ListSecretVersionIds",
    ]
    resources = [
      "arn:aws:secretsmanager:${var.region}:${data.aws_caller_identity.current.account_id}:secret:lily/*",
      # RDS-managed Aurora master secret (name is rds!cluster-…, outside the
      # lily/ prefix) — ESO syncs it into the data namespace for db clients.
      module.aurora.master_user_secret_arn,
    ]
  }
}

module "irsa_external_secrets" {
  source = "../../../modules/irsa"

  role_name            = "lily-dev-external-secrets"
  oidc_provider_arn    = module.eks.oidc_provider_arn
  oidc_provider_url    = module.eks.oidc_provider_url
  namespace            = "platform"
  service_account      = "external-secrets"
  create_inline_policy = true
  policy_json          = data.aws_iam_policy_document.external_secrets.json
}

module "irsa_ebs_csi" {
  source = "../../../modules/irsa"

  role_name           = "lily-dev-ebs-csi"
  oidc_provider_arn   = module.eks.oidc_provider_arn
  oidc_provider_url   = module.eks.oidc_provider_url
  namespace           = "kube-system"
  service_account     = "ebs-csi-controller-sa"
  managed_policy_arns = ["arn:aws:iam::aws:policy/service-role/AmazonEBSCSIDriverPolicy"]
}

# Lives here (not in the eks module) because its IRSA role depends on the
# cluster's OIDC provider — see terraform/modules/eks/addons.tf.
resource "aws_eks_addon" "ebs_csi" {
  cluster_name                = module.eks.cluster_name
  addon_name                  = "aws-ebs-csi-driver"
  service_account_role_arn    = module.irsa_ebs_csi.role_arn
  resolve_conflicts_on_create = "OVERWRITE"
}
