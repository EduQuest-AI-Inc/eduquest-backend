#!/bin/bash

set -e

echo "=========================================="
echo "Setting up EduQuest PROD Instance"
echo "=========================================="

echo "Updating system packages..."
sudo apt update && sudo apt upgrade -y

echo "Installing Python 3.11 and dependencies..."
sudo apt install -y software-properties-common
sudo add-apt-repository ppa:deadsnakes/ppa -y
sudo apt update
sudo apt install -y python3.11 python3-pip unzip awscli curl git

python3 --version

echo "Checking SSM agent..."
if ! systemctl is-active --quiet snap.amazon-ssm-agent.amazon-ssm-agent.service 2>/dev/null; then
    echo "Installing SSM agent..."
    sudo snap install amazon-ssm-agent --classic
    sudo systemctl start snap.amazon-ssm-agent.amazon-ssm-agent.service
    sudo systemctl enable snap.amazon-ssm-agent.amazon-ssm-agent.service
else
    echo "SSM agent already running"
fi

echo "Creating application directory..."
mkdir -p /home/ubuntu/eduquest-backend
cd /home/ubuntu/eduquest-backend

echo "Creating .env file..."
cat > .env <<'EOF'
FLASK_ENV=production

JWT_SECRET_KEY=prod-secret-key-CHANGE-THIS-TO-SECURE-KEY-DIFFERENT-FROM-DEV

API_GATEWAY_URL=https://ox6n5yri26.execute-api.us-east-2.amazonaws.com/prod

EOF

chmod 600 .env

echo "⚠️  IMPORTANT: Edit /home/ubuntu/eduquest-backend/.env with your actual PRODUCTION secret keys!"

echo "Creating systemd service..."
sudo tee /etc/systemd/system/eduquest-backend.service > /dev/null <<'EOF'
[Unit]
Description=EduQuest Backend Flask Application
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/eduquest-backend/app
Environment="PATH=/home/ubuntu/.local/bin:/usr/local/bin:/usr/bin:/bin"
Environment="FLASK_ENV=production"
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

sudo systemctl daemon-reload

echo ""
echo "=========================================="
echo "✅ PROD Instance Setup Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Edit .env file with your actual PRODUCTION secrets:"
echo "   sudo nano /home/ubuntu/eduquest-backend/.env"
echo ""
echo "2. The CI/CD pipeline will deploy your code automatically"
echo "   Or manually deploy for testing:"
echo "   cd /home/ubuntu/eduquest-backend"
echo "   git clone YOUR_REPO_URL app"
echo "   cd app && pip3 install -r requirements.txt"
echo "   sudo systemctl enable eduquest-backend"
echo "   sudo systemctl start eduquest-backend"
echo ""
echo "3. Check logs:"
echo "   sudo journalctl -u eduquest-backend -f"
echo ""
echo "=========================================="
