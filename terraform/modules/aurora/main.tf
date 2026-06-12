# Aurora PostgreSQL Serverless v2 (D9). Private subnets only; ingress solely
# from the EKS cluster security group — no internet path (NFR-15). The master
# password is RDS-managed in Secrets Manager (never in Terraform state);
# External Secrets consumes it via the ClusterSecretStore.

resource "aws_security_group" "this" {
  name        = "${var.name}-aurora"
  description = "Aurora Postgres - ingress only from EKS nodes"
  vpc_id      = var.vpc_id

  tags = {
    Name = "${var.name}-aurora"
  }
}

resource "aws_vpc_security_group_ingress_rule" "postgres" {
  count = length(var.allowed_security_group_ids)

  security_group_id            = aws_security_group.this.id
  referenced_security_group_id = var.allowed_security_group_ids[count.index]
  from_port                    = 5432
  to_port                      = 5432
  ip_protocol                  = "tcp"
}

# No egress rules: Aurora initiates no outbound connections.

resource "aws_db_subnet_group" "this" {
  name       = "${var.name}-aurora"
  subnet_ids = var.private_subnet_ids
}

resource "aws_rds_cluster" "this" {
  cluster_identifier = "${var.name}-aurora"
  engine             = "aurora-postgresql"
  engine_mode        = "provisioned"
  engine_version     = var.engine_version
  database_name      = var.database_name

  master_username             = var.master_username
  manage_master_user_password = true

  db_subnet_group_name   = aws_db_subnet_group.this.name
  vpc_security_group_ids = [aws_security_group.this.id]
  storage_encrypted      = true

  serverlessv2_scaling_configuration {
    min_capacity             = var.min_acu
    max_capacity             = var.max_acu
    seconds_until_auto_pause = var.min_acu == 0 ? var.auto_pause_seconds : null
  }

  # Dev posture: cheap to run, safe to destroy (cost guards over durability).
  backup_retention_period = 1
  skip_final_snapshot     = true
  deletion_protection     = false
  apply_immediately       = true
}

resource "aws_rds_cluster_instance" "this" {
  identifier         = "${var.name}-aurora-1"
  cluster_identifier = aws_rds_cluster.this.id
  instance_class     = "db.serverless"
  engine             = aws_rds_cluster.this.engine
  engine_version     = aws_rds_cluster.this.engine_version

  performance_insights_enabled = false # cost guard; revisit in Phase 4
}
