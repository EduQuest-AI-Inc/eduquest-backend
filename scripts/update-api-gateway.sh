#!/bin/bash

set -e

ENV=${1:-prod}

if [[ "$ENV" != "prod" && "$ENV" != "dev" ]]; then
  echo "Usage: $0 [prod|dev]"
  echo "Default: prod"
  exit 1
fi

STACK_NAME="eduquest-api-gateway-${ENV}"
TEMPLATE_FILE="cloudformation/api-gateway.yaml"
PARAMETERS_FILE="cloudformation/parameters-${ENV}.json"
REGION="us-east-2"

if [ ! -f "$PARAMETERS_FILE" ]; then
  echo "Error: $PARAMETERS_FILE not found"
  exit 1
fi

echo "Updating API Gateway CloudFormation Stack for ${ENV^^} environment..."

aws cloudformation deploy \
  --template-file $TEMPLATE_FILE \
  --stack-name $STACK_NAME \
  --parameter-overrides file://$PARAMETERS_FILE \
  --region $REGION \
  --capabilities CAPABILITY_IAM \
  --no-fail-on-empty-changeset

echo ""
echo "=========================================="
echo "Update Complete - ${ENV^^} Environment"
echo "=========================================="

API_GATEWAY_URL=$(aws cloudformation describe-stacks \
  --stack-name $STACK_NAME \
  --region $REGION \
  --query 'Stacks[0].Outputs[?OutputKey==`APIGatewayURL`].OutputValue' \
  --output text)

echo "API Gateway URL: $API_GATEWAY_URL"
echo "=========================================="
