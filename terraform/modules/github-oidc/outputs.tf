output "plan_role_arn" {
  description = "Role ARN for CI terraform plan — store as the AWS_PLAN_ROLE_ARN GitHub secret, never commit"
  value       = aws_iam_role.plan.arn
}
