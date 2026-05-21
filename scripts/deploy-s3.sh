#!/bin/bash

set -e

STACK_NAME="eduquest-s3"
TEMPLATE_FILE="cloudformation/s3.yaml"
PARAMETERS_FILE="cloudformation/s3-parameters-prod.json"
REGION="us-east-2"

if [ ! -f "$PARAMETERS_FILE" ]; then
  echo "Error: $PARAMETERS_FILE not found"
  echo "Copy cloudformation/s3-parameters-template.json, fill in BucketName, and save as $PARAMETERS_FILE"
  exit 1
fi

echo "Deploying S3 CloudFormation stack..."
echo ""
echo "NOTE: If the bucket already exists outside CloudFormation, use resource import instead:"
echo "  aws cloudformation create-change-set --stack-name $STACK_NAME \\"
echo "    --change-set-type IMPORT \\"
echo "    --resources-to-import '[{\"ResourceType\":\"AWS::S3::Bucket\",\"LogicalResourceId\":\"UploadsBucket\",\"ResourceIdentifier\":{\"BucketName\":\"<your-bucket>\"}}]' \\"
echo "    --template-body file://$TEMPLATE_FILE \\"
echo "    --parameters file://$PARAMETERS_FILE \\"
echo "    --change-set-name import-uploads-bucket --region $REGION"
echo ""

aws cloudformation deploy \
  --template-file $TEMPLATE_FILE \
  --stack-name $STACK_NAME \
  --parameter-overrides file://$PARAMETERS_FILE \
  --region $REGION \
  --no-fail-on-empty-changeset

echo ""
echo "=========================================="
echo "S3 Stack Deployed Successfully!"
echo "=========================================="
