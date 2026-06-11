variable "repository_names" {
  description = "ECR repository names to create (one per service image)"
  type        = set(string)
}

variable "keep_last_images" {
  description = "Number of images retained by the lifecycle policy"
  type        = number
  default     = 10
}
