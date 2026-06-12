# D12 ingestion plumbing: versioned raw-HTML bucket + crawl/index job queues.
# Key scheme (pipeline convention, documented here): raw HTML lands at
#   raw/{page_type}/dt={YYYY-MM-DD}/{sha256(url)}.html
# Bucket versioning preserves history per URL key; parsers read ONLY from S3.

resource "random_id" "suffix" {
  byte_length = 4
}

resource "aws_s3_bucket" "raw" {
  bucket = "${var.name}-raw-crawl-${random_id.suffix.hex}"
}

resource "aws_s3_bucket_versioning" "raw" {
  bucket = aws_s3_bucket.raw.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "raw" {
  bucket = aws_s3_bucket.raw.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "raw" {
  bucket = aws_s3_bucket.raw.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "raw" {
  bucket = aws_s3_bucket.raw.id

  rule {
    id     = "expire-noncurrent"
    status = "Enabled"

    filter {}

    noncurrent_version_expiration {
      noncurrent_days = var.noncurrent_version_expiry_days
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}

# ---- Queues: crawl-jobs (discovery -> fetchers), index-jobs (etl -> embed) --

resource "aws_sqs_queue" "crawl_jobs_dlq" {
  name                      = "${var.name}-crawl-jobs-dlq"
  message_retention_seconds = 1209600 # 14 days to inspect failures
}

resource "aws_sqs_queue" "crawl_jobs" {
  name                       = "${var.name}-crawl-jobs"
  visibility_timeout_seconds = var.visibility_timeout_seconds
  receive_wait_time_seconds  = 20 # long polling
  message_retention_seconds  = 345600

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.crawl_jobs_dlq.arn
    maxReceiveCount     = var.max_receive_count
  })
}

resource "aws_sqs_queue" "index_jobs_dlq" {
  name                      = "${var.name}-index-jobs-dlq"
  message_retention_seconds = 1209600
}

resource "aws_sqs_queue" "index_jobs" {
  name                       = "${var.name}-index-jobs"
  visibility_timeout_seconds = var.visibility_timeout_seconds
  receive_wait_time_seconds  = 20
  message_retention_seconds  = 345600

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.index_jobs_dlq.arn
    maxReceiveCount     = var.max_receive_count
  })
}
