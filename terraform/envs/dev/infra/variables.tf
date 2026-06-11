variable "region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "domain_name" {
  description = "Registered apex domain for the hosted zone and ACM cert"
  type        = string
}

variable "cluster_version" {
  description = "EKS Kubernetes version — verify latest standard-support version before first apply"
  type        = string
  default     = "1.33"
}

variable "admin_principal_arn" {
  description = "IAM principal granted cluster-admin (set in gitignored dev.auto.tfvars — contains the account ID)"
  type        = string
}

variable "public_access_cidrs" {
  description = "CIDRs allowed to reach the EKS public endpoint (your IP/32)"
  type        = list(string)
}

variable "github_repository" {
  description = "GitHub repository (owner/name) allowed to assume the CI plan role"
  type        = string
}

variable "state_bucket_name" {
  description = "Terraform state bucket name (from the bootstrap stack output)"
  type        = string
}
