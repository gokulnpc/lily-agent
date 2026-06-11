# Two managed node groups (no Karpenter — static sizes fit a dev cluster):
#   system          on-demand, runs platform controllers
#   stateless-spot  spot with diversified types (D17), runs app workloads

data "aws_iam_policy_document" "node_trust" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "node" {
  name               = "${var.cluster_name}-node"
  assume_role_policy = data.aws_iam_policy_document.node_trust.json
}

resource "aws_iam_role_policy_attachment" "node" {
  for_each = toset([
    "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy",
    "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy",
    "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly",
  ])

  role       = aws_iam_role.node.name
  policy_arn = each.value
}

resource "aws_eks_node_group" "system" {
  cluster_name    = aws_eks_cluster.this.name
  node_group_name = "system"
  node_role_arn   = aws_iam_role.node.arn
  subnet_ids      = var.private_subnet_ids
  capacity_type   = "ON_DEMAND"
  instance_types  = [var.system_instance_type]

  scaling_config {
    min_size     = 1
    desired_size = 2
    max_size     = 2
  }

  labels = {
    role = "system"
  }

  depends_on = [aws_iam_role_policy_attachment.node]

  lifecycle {
    ignore_changes = [scaling_config[0].desired_size] # scale-down script owns this
  }
}

resource "aws_eks_node_group" "stateless_spot" {
  cluster_name    = aws_eks_cluster.this.name
  node_group_name = "stateless-spot"
  node_role_arn   = aws_iam_role.node.arn
  subnet_ids      = var.private_subnet_ids
  capacity_type   = "SPOT"
  instance_types  = var.spot_instance_types

  scaling_config {
    min_size     = 0
    desired_size = 1
    max_size     = 3
  }

  labels = {
    role = "stateless"
  }

  depends_on = [aws_iam_role_policy_attachment.node]

  lifecycle {
    ignore_changes = [scaling_config[0].desired_size]
  }
}
