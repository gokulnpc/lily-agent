output "raw_bucket_name" {
  description = "Versioned raw-HTML bucket"
  value       = aws_s3_bucket.raw.bucket
}

output "raw_bucket_arn" {
  description = "Raw bucket ARN"
  value       = aws_s3_bucket.raw.arn
}

output "crawl_jobs_queue_url" {
  description = "Crawl jobs queue URL"
  value       = aws_sqs_queue.crawl_jobs.url
}

output "crawl_jobs_queue_arn" {
  description = "Crawl jobs queue ARN"
  value       = aws_sqs_queue.crawl_jobs.arn
}

output "index_jobs_queue_url" {
  description = "Index jobs queue URL"
  value       = aws_sqs_queue.index_jobs.url
}

output "index_jobs_queue_arn" {
  description = "Index jobs queue ARN"
  value       = aws_sqs_queue.index_jobs.arn
}
