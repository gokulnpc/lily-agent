variable "role_name" {
  description = "Name of the IAM role"
  type        = string
}

variable "oidc_provider_arn" {
  description = "ARN of the cluster's OIDC provider"
  type        = string
}

variable "oidc_provider_url" {
  description = "URL of the cluster's OIDC provider, without the https:// scheme"
  type        = string
}

variable "namespace" {
  description = "Kubernetes namespace of the service account"
  type        = string
}

variable "service_account" {
  description = "Name of the Kubernetes service account allowed to assume this role"
  type        = string
}

variable "policy_json" {
  description = "Inline IAM policy document (JSON); null to skip"
  type        = string
  default     = null
}

variable "managed_policy_arns" {
  description = "Managed policy ARNs to attach"
  type        = list(string)
  default     = []
}
