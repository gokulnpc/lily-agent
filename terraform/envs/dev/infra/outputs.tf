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

output "aurora_endpoint" {
  description = "Aurora writer endpoint"
  value       = module.aurora.endpoint
}

output "aurora_database_name" {
  description = "Initial database name"
  value       = module.aurora.database_name
}

output "aurora_master_secret_arn" {
  description = "RDS-managed credentials secret (synced into the cluster by ESO)"
  value       = module.aurora.master_user_secret_arn
}

output "raw_bucket_name" {
  description = "Versioned raw-HTML crawl bucket"
  value       = module.s3_sqs.raw_bucket_name
}

output "crawl_jobs_queue_url" {
  description = "Crawl jobs queue URL"
  value       = module.s3_sqs.crawl_jobs_queue_url
}

output "index_jobs_queue_url" {
  description = "Index jobs queue URL"
  value       = module.s3_sqs.index_jobs_queue_url
}

output "irsa_crawler_role_arn" {
  description = "IRSA role for crawler workers (data namespace)"
  value       = module.irsa_crawler.role_arn
}

output "irsa_etl_role_arn" {
  description = "IRSA role for ETL workers (data namespace)"
  value       = module.irsa_etl.role_arn
}

output "opensearch_endpoint" {
  description = "OpenSearch VPC endpoint (retrieval + logs index namespaces)"
  value       = module.opensearch.endpoint
}

output "ci_plan_role_arn" {
  description = "GitHub Actions plan role — set as the AWS_PLAN_ROLE_ARN repo secret"
  value       = module.github_oidc.plan_role_arn
}

output "guardrail_id" {
  description = "Bedrock Guardrail id — set as LILY_GUARDRAIL_ID for the orchestrator (D6)"
  value       = module.guardrail.guardrail_id
}

output "guardrail_version" {
  description = "Published guardrail version — set as LILY_GUARDRAIL_VERSION"
  value       = module.guardrail.guardrail_version
}

output "guardrail_arn" {
  description = "Guardrail ARN — for the orchestrator role's bedrock:ApplyGuardrail grant"
  value       = module.guardrail.guardrail_arn
}
