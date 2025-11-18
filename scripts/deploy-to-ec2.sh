#!/bin/bash

# Deploy Flask application to EC2 instance
# Usage: ./deploy-to-ec2.sh <environment> <ec2-instance-id>

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

# Create deployment package
echo "Creating deployment package..."
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DEPLOY_PACKAGE="eduquest-backend-${ENVIRONMENT}-${TIMESTAMP}.zip"

# Create a clean build directory
BUILD_DIR=$(mktemp -d)
trap "rm -rf $BUILD_DIR" EXIT

# Copy application files
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

# Create zip package
cd "$BUILD_DIR"
zip -r "/tmp/$DEPLOY_PACKAGE" . > /dev/null

echo "Package created: /tmp/$DEPLOY_PACKAGE"

# Copy package to EC2 using Systems Manager
echo "Uploading package to EC2..."
S3_BUCKET="eduquest-deployments-${ENVIRONMENT}"
S3_KEY="packages/$DEPLOY_PACKAGE"

# Upload to S3
aws s3 cp "/tmp/$DEPLOY_PACKAGE" "s3://${S3_BUCKET}/${S3_KEY}"

# Execute deployment on EC2 using Systems Manager
echo "Executing deployment on EC2..."
COMMAND_ID=$(aws ssm send-command \
    --instance-ids "$INSTANCE_ID" \
    --document-name "AWS-RunShellScript" \
    --parameters commands=["
        set -e
        cd /home/ubuntu/eduquest-backend

        # Backup current deployment
        if [ -d app ]; then
            mv app app.backup.\$(date +%Y%m%d_%H%M%S)
        fi

        # Download new package
        aws s3 cp s3://${S3_BUCKET}/${S3_KEY} /tmp/

        # Extract package
        mkdir -p app
        unzip -q /tmp/$DEPLOY_PACKAGE -d app/
        cd app

        # Install/update dependencies
        if [ -f requirements.txt ]; then
            pip3 install -r requirements.txt
        fi

        # Set environment
        export FLASK_ENV=${ENVIRONMENT}

        # Restart application service
        sudo systemctl restart eduquest-backend

        # Verify service is running
        sleep 5
        if systemctl is-active --quiet eduquest-backend; then
            echo 'Deployment successful'
        else
            echo 'Deployment failed - service not running'
            exit 1
        fi

        # Cleanup
        rm /tmp/$DEPLOY_PACKAGE

        # Keep only last 3 backups
        ls -t /home/ubuntu/eduquest-backend/app.backup.* 2>/dev/null | tail -n +4 | xargs rm -rf 2>/dev/null || true
    "] \
    --comment "Deploy eduquest-backend ${ENVIRONMENT}" \
    --query 'Command.CommandId' \
    --output text)

echo "Command ID: $COMMAND_ID"

# Wait for command to complete
echo "Waiting for deployment to complete..."
aws ssm wait command-executed \
    --command-id "$COMMAND_ID" \
    --instance-id "$INSTANCE_ID"

# Check command status
STATUS=$(aws ssm get-command-invocation \
    --command-id "$COMMAND_ID" \
    --instance-id "$INSTANCE_ID" \
    --query 'Status' \
    --output text)

if [ "$STATUS" == "Success" ]; then
    echo "=========================================="
    echo "Deployment completed successfully!"
    echo "=========================================="

    # Get command output
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

    # Get error output
    aws ssm get-command-invocation \
        --command-id "$COMMAND_ID" \
        --instance-id "$INSTANCE_ID" \
        --query 'StandardErrorContent' \
        --output text

    exit 1
fi
