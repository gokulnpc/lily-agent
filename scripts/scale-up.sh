#!/usr/bin/env bash
# Restore working node-group sizes after scripts/scale-down.sh.
set -euo pipefail

CLUSTER="${CLUSTER:-lily-dev}"
REGION="${AWS_REGION:-us-east-1}"

echo "scaling system to 2..."
aws eks update-nodegroup-config \
  --region "$REGION" \
  --cluster-name "$CLUSTER" \
  --nodegroup-name system \
  --scaling-config minSize=1,maxSize=2,desiredSize=2 >/dev/null

echo "scaling stateless-spot to 1..."
aws eks update-nodegroup-config \
  --region "$REGION" \
  --cluster-name "$CLUSTER" \
  --nodegroup-name stateless-spot \
  --scaling-config minSize=0,maxSize=3,desiredSize=1 >/dev/null

echo "done — nodes take ~2 min to join"
