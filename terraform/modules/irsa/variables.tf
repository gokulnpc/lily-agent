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

variable "create_inline_policy" {
  description = "Whether to attach policy_json as an inline policy. Must be a static literal — policy_json content may be unknown at plan time, so count cannot derive from it."
  type        = bool
  default     = false
}

variable "policy_json" {
  description = "Inline IAM policy document (JSON); used when create_inline_policy is true"
  type        = string
  default     = null
}

variable "managed_policy_arns" {
  description = "Managed policy ARNs to attach"
  type        = list(string)
  default     = []
}
