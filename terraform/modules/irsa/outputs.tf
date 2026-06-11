output "role_arn" {
  description = "ARN of the IRSA role — annotate the service account with this"
  value       = aws_iam_role.this.arn
}
