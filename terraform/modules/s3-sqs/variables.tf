variable "name" {
  description = "Name prefix for bucket and queues"
  type        = string
}

variable "noncurrent_version_expiry_days" {
  description = "Days to keep noncurrent raw-HTML object versions (history for re-parsing)"
  type        = number
  default     = 60
}

variable "visibility_timeout_seconds" {
  description = "SQS visibility timeout — must exceed the slowest Playwright fetch + S3 write"
  type        = number
  default     = 300
}

variable "max_receive_count" {
  description = "Receives before a message moves to the DLQ"
  type        = number
  default     = 5
}
