variable "github_repository" {
  description = "GitHub repository allowed to assume the CI roles, as owner/name"
  type        = string
}

variable "state_bucket_name" {
  description = "Terraform state bucket the plan role may read (and lock)"
  type        = string
}
