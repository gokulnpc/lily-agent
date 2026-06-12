output "endpoint" {
  description = "Writer endpoint"
  value       = aws_rds_cluster.this.endpoint
}

output "reader_endpoint" {
  description = "Reader endpoint"
  value       = aws_rds_cluster.this.reader_endpoint
}

output "port" {
  description = "Postgres port"
  value       = aws_rds_cluster.this.port
}

output "database_name" {
  description = "Initial database name"
  value       = aws_rds_cluster.this.database_name
}

output "master_user_secret_arn" {
  description = "RDS-managed Secrets Manager secret (username/password) — grant ESO read on this"
  value       = aws_rds_cluster.this.master_user_secret[0].secret_arn
}

output "security_group_id" {
  description = "Aurora security group"
  value       = aws_security_group.this.id
}
