#!/bin/bash
set -e

echo "============================================"
echo "Creating New Dev EC2 Instance"
echo "============================================"

REGION="us-east-2"
INSTANCE_PROFILE="EduQuest-EC2-InstanceProfile"

# Get the latest Ubuntu 24.04 LTS AMI
echo "Finding latest Ubuntu 24.04 LTS AMI..."
AMI_ID=$(aws ec2 describe-images \
  --region $REGION \
  --owners 099720109477 \
  --filters \
    "Name=name,Values=ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*" \
    "Name=state,Values=available" \
  --query 'sort_by(Images, &CreationDate)[-1].ImageId' \
  --output text)

echo "Using AMI: $AMI_ID"

# Get default VPC and subnet
VPC_ID=$(aws ec2 describe-vpcs \
  --region $REGION \
  --filters "Name=is-default,Values=true" \
  --query 'Vpcs[0].VpcId' \
  --output text)

SUBNET_ID=$(aws ec2 describe-subnets \
  --region $REGION \
  --filters "Name=vpc-id,Values=$VPC_ID" \
  --query 'Subnets[0].SubnetId' \
  --output text)

# Get existing security group from old instance
echo "Getting security group from old instance..."
SECURITY_GROUP_ID=$(aws ec2 describe-instances \
  --region $REGION \
  --instance-ids i-02c46d8036081b9df \
  --query 'Reservations[0].Instances[0].SecurityGroups[0].GroupId' \
  --output text 2>/dev/null || echo "")

if [ -z "$SECURITY_GROUP_ID" ] || [ "$SECURITY_GROUP_ID" = "None" ]; then
  echo "Could not get security group from old instance, using default..."
  SECURITY_GROUP_ID=$(aws ec2 describe-security-groups \
    --region $REGION \
    --filters "Name=vpc-id,Values=$VPC_ID" \
    --query 'SecurityGroups[0].GroupId' \
    --output text)
fi

echo "Configuration:"
echo "  AMI ID: $AMI_ID"
echo "  Subnet ID: $SUBNET_ID"
echo "  Security Group: $SECURITY_GROUP_ID"

# User Data for SSM Agent setup
USER_DATA='#!/bin/bash
apt-get update -y
snap install amazon-ssm-agent --classic
snap start amazon-ssm-agent
apt-get install -y python3-pip python3-venv unzip awscli
mkdir -p /home/ubuntu/eduquest-backend
chown ubuntu:ubuntu /home/ubuntu/eduquest-backend'

# Launch instance
echo "Launching new instance..."
INSTANCE_ID=$(aws ec2 run-instances \
  --region $REGION \
  --image-id $AMI_ID \
  --instance-type t2.micro \
  --subnet-id $SUBNET_ID \
  --security-group-ids $SECURITY_GROUP_ID \
  --iam-instance-profile Name=$INSTANCE_PROFILE \
  --user-data "$USER_DATA" \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=eduquest-backend-dev},{Key=Environment,Value=dev}]' \
  --query 'Instances[0].InstanceId' \
  --output text)

echo "============================================"
echo "Instance created: $INSTANCE_ID"
echo "============================================"

echo "Waiting for instance to be running..."
aws ec2 wait instance-running --region $REGION --instance-ids $INSTANCE_ID

echo "Getting instance details..."
aws ec2 describe-instances \
  --region $REGION \
  --instance-ids $INSTANCE_ID \
  --query 'Reservations[0].Instances[0].{InstanceId:InstanceId,State:State.Name,PrivateIP:PrivateIpAddress,PublicIP:PublicIpAddress}' \
  --output table

echo ""
echo "Waiting for SSM Agent to come online (this may take 2-3 minutes)..."
for i in {1..30}; do
  SSM_STATUS=$(aws ssm describe-instance-information \
    --region $REGION \
    --filters "Key=InstanceIds,Values=$INSTANCE_ID" \
    --query 'InstanceInformationList[0].PingStatus' \
    --output text 2>/dev/null || echo "None")

  if [ "$SSM_STATUS" = "Online" ]; then
    echo "✓ SSM Agent is online!"

    # Test SSM
    echo "Testing SSM Run Command..."
    TEST_CMD=$(aws ssm send-command \
      --region $REGION \
      --instance-ids $INSTANCE_ID \
      --document-name "AWS-RunShellScript" \
      --parameters commands="echo SSM_Test_Successful" \
      --output text \
      --query 'Command.CommandId')

    sleep 5

    TEST_RESULT=$(aws ssm get-command-invocation \
      --region $REGION \
      --command-id $TEST_CMD \
      --instance-id $INSTANCE_ID \
      --query 'StandardOutputContent' \
      --output text 2>/dev/null || echo "")

    if echo "$TEST_RESULT" | grep -q "SSM_Test_Successful"; then
      echo "✓ SSM Run Command test successful!"
    fi

    break
  fi

  echo "Waiting... ($i/30)"
  sleep 10
done

echo ""
echo "============================================"
echo "Setup Complete!"
echo "============================================"
echo "New Instance ID: $INSTANCE_ID"
echo ""
echo "Ready for deployment!"
