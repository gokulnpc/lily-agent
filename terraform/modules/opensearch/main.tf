# One OpenSearch domain (D10), VPC-only (NFR-15): private subnets, ingress
# solely from the EKS cluster SG, IAM-signed access from the pipeline IRSA roles.
# Serves double duty via index namespaces: retrieval-* (RAG) and logs-* (Kibana,
# Phase 4) — the access policy and index naming keep them separate, one domain.

resource "aws_security_group" "this" {
  name        = "${var.name}-opensearch"
  description = "OpenSearch - ingress only from EKS nodes"
  vpc_id      = var.vpc_id

  tags = {
    Name = "${var.name}-opensearch"
  }
}

resource "aws_vpc_security_group_ingress_rule" "https" {
  count = length(var.allowed_security_group_ids)

  security_group_id            = aws_security_group.this.id
  referenced_security_group_id = var.allowed_security_group_ids[count.index]
  from_port                    = 443
  to_port                      = 443
  ip_protocol                  = "tcp"
}

# Service-linked role for VPC domains. Account-global and created once ever —
# set create_service_linked_role=false (or import) if the account already has it.
resource "aws_iam_service_linked_role" "os" {
  count            = var.create_service_linked_role ? 1 : 0
  aws_service_name = "opensearchservice.amazonaws.com"
  description      = "Service-linked role for OpenSearch VPC domains"
}

resource "aws_opensearch_domain" "this" {
  domain_name    = var.name
  engine_version = var.engine_version

  cluster_config {
    instance_type          = var.instance_type
    instance_count         = var.instance_count
    zone_awareness_enabled = false # single-node dev
  }

  ebs_options {
    ebs_enabled = true
    volume_type = "gp3"
    volume_size = var.volume_size_gb
  }

  vpc_options {
    subnet_ids         = slice(var.subnet_ids, 0, var.instance_count)
    security_group_ids = [aws_security_group.this.id]
  }

  encrypt_at_rest {
    enabled = true
  }

  node_to_node_encryption {
    enabled = true
  }

  domain_endpoint_options {
    enforce_https       = true
    tls_security_policy = "Policy-Min-TLS-1-2-PFS-2023-10"
  }

  # IAM access policy: only the named IRSA principals, SigV4-signed. No
  # fine-grained access control / master user for dev (avoids the extra secret).
  access_policies = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect    = "Allow"
        Principal = { AWS = var.access_principal_arns }
        Action    = "es:ESHttp*"
        Resource  = "arn:aws:es:*:*:domain/${var.name}/*"
      }
    ]
  })

  depends_on = [aws_iam_service_linked_role.os]
}
