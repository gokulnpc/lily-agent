variable "name" {
  description = "Name prefix for all network resources"
  type        = string
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.40.0.0/16"
}

variable "availability_zones" {
  description = "AZs to spread subnets across (2 minimum for EKS)"
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b"]
}

variable "cluster_name" {
  description = "EKS cluster name, used for subnet discovery tags"
  type        = string
}
