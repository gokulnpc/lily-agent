output "endpoint" {
  description = "Domain VPC endpoint (https)"
  value       = aws_opensearch_domain.this.endpoint
}

output "arn" {
  description = "Domain ARN"
  value       = aws_opensearch_domain.this.arn
}

output "security_group_id" {
  description = "OpenSearch security group"
  value       = aws_security_group.this.id
}
