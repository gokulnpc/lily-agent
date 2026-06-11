output "cluster_name" {
  description = "EKS cluster name"
  value       = aws_eks_cluster.this.name
}

output "cluster_endpoint" {
  description = "Kubernetes API endpoint"
  value       = aws_eks_cluster.this.endpoint
}

output "cluster_certificate_authority_data" {
  description = "Base64-encoded cluster CA certificate"
  value       = aws_eks_cluster.this.certificate_authority[0].data
}

output "oidc_provider_arn" {
  description = "ARN of the cluster OIDC provider (IRSA trust anchor)"
  value       = aws_iam_openid_connect_provider.this.arn
}

output "oidc_provider_url" {
  description = "OIDC issuer URL without the https:// scheme (IRSA condition keys)"
  value       = trimprefix(aws_eks_cluster.this.identity[0].oidc[0].issuer, "https://")
}
