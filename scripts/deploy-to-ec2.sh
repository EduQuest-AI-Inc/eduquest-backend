#!/bin/bash

set -e

ENVIRONMENT=$1
INSTANCE_ID=$2

if [ -z "$ENVIRONMENT" ] || [ -z "$INSTANCE_ID" ]; then
    echo "Usage: $0 <environment> <ec2-instance-id>"
    echo "Example: $0 dev i-1234567890abcdef0"
    exit 1
fi

echo "=========================================="
echo "Deploying to EC2 Instance: $INSTANCE_ID"
echo "Environment: $ENVIRONMENT"
echo "=========================================="

echo "Creating deployment package..."
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DEPLOY_PACKAGE="eduquest-backend-${ENVIRONMENT}-${TIMESTAMP}.zip"

BUILD_DIR=$(mktemp -d)
trap "rm -rf $BUILD_DIR" EXIT

echo "Copying application files..."
rsync -av --exclude='__pycache__' \
          --exclude='*.pyc' \
          --exclude='.git' \
          --exclude='.env' \
          --exclude='node_modules' \
          --exclude='venv' \
          --exclude='.pytest_cache' \
          --exclude='*.log' \
          . "$BUILD_DIR/"

cd "$BUILD_DIR"
zip -r "/tmp/$DEPLOY_PACKAGE" . > /dev/null

echo "Package created: /tmp/$DEPLOY_PACKAGE"

echo "Uploading package to EC2..."
S3_BUCKET="eduquest-deployments-${ENVIRONMENT}"
S3_KEY="packages/$DEPLOY_PACKAGE"

aws s3 cp "/tmp/$DEPLOY_PACKAGE" "s3://${S3_BUCKET}/${S3_KEY}"

echo "Executing deployment on EC2..."
COMMAND_ID=$(aws ssm send-command \
    --instance-ids "$INSTANCE_ID" \
    --document-name "AWS-RunShellScript" \
    --parameters commands=["
        set -e
        cd /home/ubuntu/eduquest-backend

        if [ -d app ]; then
            mv app app.backup.\$(date +%Y%m%d_%H%M%S)
        fi

        aws s3 cp s3://${S3_BUCKET}/${S3_KEY} /tmp/

        mkdir -p app
        unzip -q /tmp/$DEPLOY_PACKAGE -d app/
        cd app

        if [ -f requirements.txt ]; then
            pip3 install -r requirements.txt
        fi

        export FLASK_ENV=${ENVIRONMENT}

        sudo systemctl restart eduquest-backend

        sleep 5
        if systemctl is-active --quiet eduquest-backend; then
            echo 'Deployment successful'
        else
            echo 'Deployment failed - service not running'
            exit 1
        fi

        rm /tmp/$DEPLOY_PACKAGE

        ls -t /home/ubuntu/eduquest-backend/app.backup.* 2>/dev/null | tail -n +4 | xargs rm -rf 2>/dev/null || true
    "] \
    --comment "Deploy eduquest-backend ${ENVIRONMENT}" \
    --query 'Command.CommandId' \
    --output text)

echo "Command ID: $COMMAND_ID"

echo "Waiting for deployment to complete..."
aws ssm wait command-executed \
    --command-id "$COMMAND_ID" \
    --instance-id "$INSTANCE_ID"

STATUS=$(aws ssm get-command-invocation \
    --command-id "$COMMAND_ID" \
    --instance-id "$INSTANCE_ID" \
    --query 'Status' \
    --output text)

if [ "$STATUS" == "Success" ]; then
    echo "=========================================="
    echo "Deployment completed successfully!"
    echo "=========================================="

    aws ssm get-command-invocation \
        --command-id "$COMMAND_ID" \
        --instance-id "$INSTANCE_ID" \
        --query 'StandardOutputContent' \
        --output text

    exit 0
else
    echo "=========================================="
    echo "Deployment failed with status: $STATUS"
    echo "=========================================="

    aws ssm get-command-invocation \
        --command-id "$COMMAND_ID" \
        --instance-id "$INSTANCE_ID" \
        --query 'StandardErrorContent' \
        --output text

    exit 1
fi
