terraform {
  backend "s3" {
    # Replace with the bucket name from `terraform output state_bucket_name`
    # in terraform/bootstrap after its one-time apply.
    bucket       = "lily-tfstate-REPLACE_AFTER_BOOTSTRAP"
    key          = "dev/infra.tfstate"
    region       = "us-east-1"
    use_lockfile = true
  }
}
