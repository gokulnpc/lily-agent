# Phase 1 data plane: Aurora + ingestion plumbing (S3/SQS) + pipeline IRSA.

module "aurora" {
  source = "../../../modules/aurora"

  name               = "lily-dev"
  vpc_id             = module.network.vpc_id
  private_subnet_ids = module.network.private_subnet_ids
  # The ONLY ingress: EKS nodes. Not internet-reachable (NFR-15).
  allowed_security_group_ids = [module.eks.cluster_security_group_id]

  min_acu = var.aurora_min_acu
  max_acu = var.aurora_max_acu
}

module "s3_sqs" {
  source = "../../../modules/s3-sqs"

  name = "lily-dev"
}

# ---- Pipeline worker IRSA (namespace: data) ---------------------------------

data "aws_iam_policy_document" "crawler" {
  statement {
    sid = "ConsumeAndFeedCrawlQueue"
    actions = [
      "sqs:ReceiveMessage",
      "sqs:DeleteMessage",
      "sqs:ChangeMessageVisibility",
      "sqs:GetQueueAttributes",
      "sqs:SendMessage", # discovery enqueues newly found URLs
    ]
    resources = [module.s3_sqs.crawl_jobs_queue_arn]
  }

  statement {
    sid       = "WriteRawHtml"
    actions   = ["s3:PutObject", "s3:GetObject"]
    resources = ["${module.s3_sqs.raw_bucket_arn}/raw/*"]
  }

  statement {
    sid       = "ListRawBucket"
    actions   = ["s3:ListBucket"]
    resources = [module.s3_sqs.raw_bucket_arn]
  }
}

module "irsa_crawler" {
  source = "../../../modules/irsa"

  role_name            = "lily-dev-crawler"
  oidc_provider_arn    = module.eks.oidc_provider_arn
  oidc_provider_url    = module.eks.oidc_provider_url
  namespace            = "data"
  service_account      = "crawler"
  create_inline_policy = true
  policy_json          = data.aws_iam_policy_document.crawler.json
}

data "aws_iam_policy_document" "etl" {
  statement {
    sid       = "ReadRawHtml"
    actions   = ["s3:GetObject", "s3:GetObjectVersion"]
    resources = ["${module.s3_sqs.raw_bucket_arn}/raw/*"]
  }

  statement {
    sid       = "ListRawBucket"
    actions   = ["s3:ListBucket", "s3:ListBucketVersions"]
    resources = [module.s3_sqs.raw_bucket_arn]
  }

  statement {
    sid = "IndexJobsQueue"
    actions = [
      "sqs:ReceiveMessage",
      "sqs:DeleteMessage",
      "sqs:ChangeMessageVisibility",
      "sqs:GetQueueAttributes",
      "sqs:SendMessage",
    ]
    resources = [module.s3_sqs.index_jobs_queue_arn]
  }
  # Bedrock (Titan embeddings) permissions arrive with the indexing step.
}

module "irsa_etl" {
  source = "../../../modules/irsa"

  role_name            = "lily-dev-etl"
  oidc_provider_arn    = module.eks.oidc_provider_arn
  oidc_provider_url    = module.eks.oidc_provider_url
  namespace            = "data"
  service_account      = "etl"
  create_inline_policy = true
  policy_json          = data.aws_iam_policy_document.etl.json
}
