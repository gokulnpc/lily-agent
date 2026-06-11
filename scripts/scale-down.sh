#!/usr/bin/env bash
# D17 overnight cost guard: scale both node groups to zero.
# Control plane (~$73/mo), NAT (~$32/mo) and the ALB keep billing — run
# `terraform destroy` on platform+infra instead when idle for days.
set -euo pipefail

CLUSTER="${CLUSTER:-lily-dev}"
REGION="${AWS_REGION:-us-east-1}"

for ng in system stateless-spot; do
  echo "scaling $ng to 0..."
  aws eks update-nodegroup-config \
    --region "$REGION" \
    --cluster-name "$CLUSTER" \
    --nodegroup-name "$ng" \
    --scaling-config minSize=0,maxSize=1,desiredSize=0 >/dev/null
done

echo "done — restore with scripts/scale-up.sh"
