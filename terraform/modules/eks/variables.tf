variable "cluster_name" {
  description = "EKS cluster name"
  type        = string
}

variable "cluster_version" {
  description = "Kubernetes version, pinned — upgrades are deliberate PRs"
  type        = string
}

variable "private_subnet_ids" {
  description = "Private subnets for the cluster and node groups"
  type        = list(string)
}

variable "public_access_cidrs" {
  description = "CIDRs allowed to reach the public API endpoint (owner IP only)"
  type        = list(string)
}

variable "admin_principal_arn" {
  description = "IAM principal granted cluster-admin via an access entry"
  type        = string
}

variable "system_instance_type" {
  description = "On-demand instance type for the system node group"
  type        = string
  default     = "t3.medium"
}

variable "spot_instance_types" {
  description = "Diversified instance types for the spot node group (D17)"
  type        = list(string)
  default     = ["t3.medium", "t3a.medium", "t3.large"]
}
