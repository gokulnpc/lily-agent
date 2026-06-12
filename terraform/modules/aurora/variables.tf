variable "name" {
  description = "Cluster identifier prefix"
  type        = string
}

variable "engine_version" {
  description = "Aurora PostgreSQL engine version (pin; verify availability before bumping)"
  type        = string
  default     = "16.13"
}

variable "database_name" {
  description = "Initial database name"
  type        = string
  default     = "lily"
}

variable "master_username" {
  description = "Master username (password is RDS-managed in Secrets Manager, never in state)"
  type        = string
  default     = "lily_admin"
}

variable "vpc_id" {
  description = "VPC for the cluster security group"
  type        = string
}

variable "private_subnet_ids" {
  description = "Private subnets for the DB subnet group (NFR-15: never internet-reachable)"
  type        = list(string)
}

variable "allowed_security_group_ids" {
  description = "Security groups allowed to reach Postgres (the EKS cluster SG) — the ONLY ingress"
  type        = list(string)
}

variable "min_acu" {
  description = "Serverless v2 floor. 0.5 per locked D9; 0 enables auto-pause (overnight $0 compute, ~15s cold resume)"
  type        = number
  default     = 0.5
}

variable "max_acu" {
  description = "Serverless v2 ceiling"
  type        = number
  default     = 2
}

variable "auto_pause_seconds" {
  description = "Idle seconds before auto-pause; only effective when min_acu = 0"
  type        = number
  default     = 600
}
