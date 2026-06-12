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
    # GetObject for the normal parse path; PutObject because the bounded
    # seed-crawl orchestrator (lily_etl.tools.seed_crawl) fetches AND parses in
    # one process, so it writes raw HTML too (the crawler role's job).
    sid       = "ReadWriteRawHtml"
    actions   = ["s3:GetObject", "s3:GetObjectVersion", "s3:PutObject"]
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

  statement {
    sid     = "OpenSearchIndexing"
    actions = ["es:ESHttpGet", "es:ESHttpPut", "es:ESHttpPost", "es:ESHttpHead"]
    # Constructed ARN (not module.opensearch.arn) to avoid a dependency cycle:
    # the domain's access policy already references this role.
    resources = [
      "arn:aws:es:${var.region}:${data.aws_caller_identity.current.account_id}:domain/lily-dev/*",
    ]
  }

  statement {
    sid     = "BedrockTitanEmbeddings"
    actions = ["bedrock:InvokeModel"]
    # Titan Embeddings v2 (D3), plus cross-region inference profile prefix.
    resources = [
      "arn:aws:bedrock:*::foundation-model/amazon.titan-embed-text-v2:0",
    ]
  }
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

module "opensearch" {
  source = "../../../modules/opensearch"

  name                       = "lily-dev"
  vpc_id                     = module.network.vpc_id
  subnet_ids                 = module.network.private_subnet_ids
  allowed_security_group_ids = [module.eks.cluster_security_group_id]
  # The indexer (etl) signs requests; Phase 2 retrieval role joins this list.
  access_principal_arns = [module.irsa_etl.role_arn]
}
