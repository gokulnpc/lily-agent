data "terraform_remote_state" "infra" {
  backend = "s3"

  config = {
    bucket = var.state_bucket_name
    key    = "dev/infra.tfstate"
    region = var.region
  }
}

locals {
  cluster_name = data.terraform_remote_state.infra.outputs.cluster_name
  infra        = data.terraform_remote_state.infra.outputs
}
