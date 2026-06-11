provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project   = "lily"
      Env       = "dev"
      ManagedBy = "terraform"
    }
  }
}
