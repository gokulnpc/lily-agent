output "guardrail_id" {
  description = "Guardrail identifier (set as LILY_GUARDRAIL_ID for the orchestrator)"
  value       = aws_bedrock_guardrail.this.guardrail_id
}

output "guardrail_arn" {
  description = "Guardrail ARN (for IAM ApplyGuardrail permission)"
  value       = aws_bedrock_guardrail.this.guardrail_arn
}

output "guardrail_version" {
  description = "Published version (set as LILY_GUARDRAIL_VERSION; app defaults to DRAFT)"
  value       = aws_bedrock_guardrail_version.this.version
}
