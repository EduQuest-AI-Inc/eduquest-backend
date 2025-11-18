#!/bin/bash

set -e

ENV=${1:-prod}

if [[ "$ENV" != "prod" && "$ENV" != "dev" ]]; then
  echo "Usage: $0 [prod|dev]"
  echo "Default: prod"
  exit 1
fi

STACK_NAME="eduquest-api-gateway-${ENV}"
REGION="us-east-2"

echo "Deleting API Gateway CloudFormation Stack for ${ENV^^} environment..."

read -p "Are you sure you want to delete the ${ENV^^} API Gateway? (yes/no): " confirmation

if [[ "$confirmation" != "yes" ]]; then
  echo "Deletion cancelled"
  exit 0
fi

aws cloudformation delete-stack \
  --stack-name $STACK_NAME \
  --region $REGION

echo "Waiting for stack deletion to complete..."
aws cloudformation wait stack-delete-complete \
  --stack-name $STACK_NAME \
  --region $REGION

echo ""
echo "=========================================="
echo "${ENV^^} Stack Deleted Successfully!"
echo "=========================================="
