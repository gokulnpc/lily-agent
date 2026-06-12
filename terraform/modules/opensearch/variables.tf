variable "name" {
  description = "Domain name prefix"
  type        = string
}

variable "engine_version" {
  description = "OpenSearch engine version"
  type        = string
  default     = "OpenSearch_2.17"
}

variable "instance_type" {
  description = "Data node type. Smallest kNN-capable single node for dev (D10/NFR-10)"
  type        = string
  default     = "t3.small.search"
}

variable "instance_count" {
  description = "Data node count (1 = single-node dev, no HA)"
  type        = number
  default     = 1
}

variable "volume_size_gb" {
  description = "EBS gp3 volume per node"
  type        = number
  default     = 10
}

variable "vpc_id" {
  description = "VPC for the domain security group"
  type        = string
}

variable "subnet_ids" {
  description = "Private subnets (NFR-15: never internet-reachable). One subnet for single-node."
  type        = list(string)
}

variable "allowed_security_group_ids" {
  description = "Security groups allowed to reach the domain (EKS cluster SG) — the ONLY ingress"
  type        = list(string)
}

variable "access_principal_arns" {
  description = "IAM role ARNs (IRSA) allowed to call the domain; requests must be SigV4-signed"
  type        = list(string)
}

variable "create_service_linked_role" {
  description = "Create the account-global OpenSearch service-linked role. Set false if it already exists."
  type        = bool
  default     = true
}
