terraform {
  backend "s3" {
    # Same bucket as the infra stack — from terraform/bootstrap output.
    bucket       = "lily-tfstate-REPLACE_AFTER_BOOTSTRAP"
    key          = "dev/platform.tfstate"
    region       = "us-east-1"
    use_lockfile = true
  }
}
