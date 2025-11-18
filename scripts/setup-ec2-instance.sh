#!/bin/bash

# Setup script for EduQuest EC2 instances
# Run this script on each EC2 instance (dev and prod)

set -e

echo "=========================================="
echo "EduQuest EC2 Instance Setup"
echo "=========================================="

# Prompt for environment
read -p "Enter environment (dev/prod): " ENVIRONMENT

if [[ "$ENVIRONMENT" != "dev" && "$ENVIRONMENT" != "prod" ]]; then
    echo "Error: Environment must be 'dev' or 'prod'"
    exit 1
fi

echo "Setting up $ENVIRONMENT environment..."

# Update system
echo "Updating system packages..."
sudo apt update && sudo apt upgrade -y

# Install Python 3.11
echo "Installing Python 3.11..."
sudo apt install software-properties-common -y
sudo add-apt-repository ppa:deadsnakes/ppa -y
sudo apt update
sudo apt install python3.11 python3.11-venv python3-pip unzip awscli curl -y

# Verify Python installation
python3.11 --version

# Install AWS Systems Manager Agent
echo "Installing AWS Systems Manager Agent..."
if ! systemctl is-active --quiet snap.amazon-ssm-agent.amazon-ssm-agent.service; then
    sudo snap install amazon-ssm-agent --classic
    sudo systemctl start snap.amazon-ssm-agent.amazon-ssm-agent.service
    sudo systemctl enable snap.amazon-ssm-agent.amazon-ssm-agent.service
    echo "SSM Agent installed and started"
else
    echo "SSM Agent already running"
fi

# Verify SSM agent is running
sudo systemctl status snap.amazon-ssm-agent.amazon-ssm-agent.service --no-pager

# Create application directory
echo "Creating application directory..."
mkdir -p /home/ubuntu/eduquest-backend
cd /home/ubuntu/eduquest-backend

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "Creating .env file..."
    cat > .env <<EOF
# Environment Configuration
FLASK_ENV=$ENVIRONMENT

# JWT Configuration
JWT_SECRET_KEY=change-this-to-a-secure-secret-key

# API Gateway URL (update after CloudFormation deployment)
API_GATEWAY_URL=https://your-api-gateway-url.execute-api.us-east-2.amazonaws.com/$ENVIRONMENT

# Add your other environment variables below:
# Firebase credentials, OpenAI API keys, database URLs, etc.
EOF

    echo ""
    echo "⚠️  IMPORTANT: Edit /home/ubuntu/eduquest-backend/.env with your actual values"
    echo ""
fi

# Set proper permissions
chmod 600 .env

# Create systemd service
echo "Creating systemd service..."
sudo tee /etc/systemd/system/eduquest-backend.service > /dev/null <<EOF
[Unit]
Description=EduQuest Backend Flask Application
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/eduquest-backend/app
Environment="PATH=/home/ubuntu/.local/bin:/usr/local/bin:/usr/bin:/bin"
Environment="FLASK_ENV=$ENVIRONMENT"
EnvironmentFile=/home/ubuntu/eduquest-backend/.env
ExecStart=/usr/bin/python3 /home/ubuntu/eduquest-backend/app/app.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=eduquest-backend

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd
sudo systemctl daemon-reload

echo ""
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Edit .env file with your actual configuration:"
echo "   nano /home/ubuntu/eduquest-backend/.env"
echo ""
echo "2. Deploy your application code to /home/ubuntu/eduquest-backend/app/"
echo "   (This will be done automatically by the CI/CD pipeline)"
echo ""
echo "3. After deployment, enable and start the service:"
echo "   sudo systemctl enable eduquest-backend"
echo "   sudo systemctl start eduquest-backend"
echo ""
echo "4. Check service status:"
echo "   sudo systemctl status eduquest-backend"
echo ""
echo "5. View logs:"
echo "   sudo journalctl -u eduquest-backend -f"
echo ""
echo "=========================================="
