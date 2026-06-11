# Public hosted zone + one ACM certificate covering the apex and both wildcard
# levels. Issued in us-east-1, so the same cert serves the ALB now and
# CloudFront in Phase 3 (D8).
#
# If the domain was registered in Route53, point the registered domain's name
# servers at this zone's NS set after the first apply (runbook step) —
# otherwise ACM DNS validation never completes.

resource "aws_route53_zone" "this" {
  name = var.domain_name
}

resource "aws_acm_certificate" "this" {
  domain_name = var.domain_name
  subject_alternative_names = [
    "*.${var.domain_name}",
    "*.dev.${var.domain_name}",
  ]
  validation_method = "DNS"

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_route53_record" "validation" {
  for_each = {
    for dvo in aws_acm_certificate.this.domain_validation_options : dvo.domain_name => {
      name   = dvo.resource_record_name
      type   = dvo.resource_record_type
      record = dvo.resource_record_value
    }
  }

  zone_id         = aws_route53_zone.this.zone_id
  name            = each.value.name
  type            = each.value.type
  records         = [each.value.record]
  ttl             = 60
  allow_overwrite = true
}

resource "aws_acm_certificate_validation" "this" {
  certificate_arn         = aws_acm_certificate.this.arn
  validation_record_fqdns = [for record in aws_route53_record.validation : record.fqdn]
}
