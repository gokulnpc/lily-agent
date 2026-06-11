output "zone_id" {
  description = "Hosted zone ID"
  value       = aws_route53_zone.this.zone_id
}

output "zone_name_servers" {
  description = "NS set to configure on the domain registrar"
  value       = aws_route53_zone.this.name_servers
}

output "certificate_arn" {
  description = "Validated ACM certificate ARN (apex + *.domain + *.dev.domain)"
  value       = aws_acm_certificate_validation.this.certificate_arn
}
