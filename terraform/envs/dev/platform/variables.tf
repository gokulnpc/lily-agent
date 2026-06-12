variable "region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "state_bucket_name" {
  description = "Terraform state bucket (from the bootstrap stack output)"
  type        = string
}

variable "acme_email" {
  description = "Email for Let's Encrypt registration (expiry notices)"
  type        = string
}

variable "alb_controller_chart_version" {
  description = "eks/aws-load-balancer-controller chart version"
  type        = string
  default     = "3.4.0"
}

variable "cert_manager_chart_version" {
  description = "jetstack/cert-manager chart version"
  type        = string
  default     = "v1.20.2"
}

variable "external_secrets_chart_version" {
  description = "external-secrets/external-secrets chart version"
  type        = string
  default     = "2.6.0"
}

# ---- Observability (Phase 4) ----
variable "kube_prometheus_stack_chart_version" {
  description = "prometheus-community/kube-prometheus-stack chart version"
  type        = string
  default     = "75.18.0"
}

variable "jaeger_chart_version" {
  description = "jaegertracing/jaeger chart version (all-in-one, in-memory)"
  type        = string
  default     = "3.4.1"
}

variable "fluent_bit_chart_version" {
  description = "fluent/fluent-bit chart version"
  type        = string
  default     = "0.47.10"
}
