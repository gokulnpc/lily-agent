# One-time bootstrap: the S3 bucket that holds all other stacks' remote state.
# This stack itself uses LOCAL state (gitignored) — apply once, record the bucket
# name in the main stacks' backend blocks, and leave it alone.

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

resource "random_id" "suffix" {
  byte_length = 4
}

resource "aws_s3_bucket" "tfstate" {
  bucket = "lily-tfstate-${random_id.suffix.hex}"

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket_versioning" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
