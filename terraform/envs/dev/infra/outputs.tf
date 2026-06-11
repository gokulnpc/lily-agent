output "cluster_name" {
  description = "EKS cluster name"
  value       = module.eks.cluster_name
}

output "cluster_endpoint" {
  description = "Kubernetes API endpoint"
  value       = module.eks.cluster_endpoint
}

output "cluster_certificate_authority_data" {
  description = "Cluster CA certificate (base64)"
  value       = module.eks.cluster_certificate_authority_data
}

output "vpc_id" {
  description = "VPC ID"
  value       = module.network.vpc_id
}

output "zone_id" {
  description = "Route53 hosted zone ID"
  value       = module.dns.zone_id
}

output "zone_name_servers" {
  description = "NS set to configure on the domain registrar after first apply"
  value       = module.dns.zone_name_servers
}

output "certificate_arn" {
  description = "Validated ACM certificate ARN for the ALB ingress"
  value       = module.dns.certificate_arn
}

output "ecr_repository_urls" {
  description = "ECR repository URLs by service name"
  value       = module.ecr.repository_urls
}

output "irsa_alb_controller_role_arn" {
  description = "IRSA role for the AWS Load Balancer Controller"
  value       = module.irsa_alb_controller.role_arn
}

output "irsa_cert_manager_role_arn" {
  description = "IRSA role for cert-manager (Route53 DNS-01)"
  value       = module.irsa_cert_manager.role_arn
}

output "irsa_external_secrets_role_arn" {
  description = "IRSA role for External Secrets Operator"
  value       = module.irsa_external_secrets.role_arn
}

output "ci_plan_role_arn" {
  description = "GitHub Actions plan role — set as the AWS_PLAN_ROLE_ARN repo secret"
  value       = module.github_oidc.plan_role_arn
}
