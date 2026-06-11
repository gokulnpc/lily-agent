output "state_bucket_name" {
  description = "Name of the S3 bucket holding remote state — paste into each stack's backend block"
  value       = aws_s3_bucket.tfstate.bucket
}
