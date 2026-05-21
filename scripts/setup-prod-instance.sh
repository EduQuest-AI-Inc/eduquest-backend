#!/bin/bash

set -e

echo "=========================================="
echo "Setting up EduQuest PROD Instance"
echo "=========================================="

echo "Creating 2 GiB swap file..."
SWAP_FILE=/swapfile
if [ ! -f "$SWAP_FILE" ]; then
    fallocate -l 2G $SWAP_FILE || dd if=/dev/zero of=$SWAP_FILE bs=128M count=16
    chmod 600 $SWAP_FILE
    mkswap $SWAP_FILE
    swapon $SWAP_FILE
    echo "$SWAP_FILE none swap sw 0 0" >> /etc/fstab
    echo "Swap created and enabled"
else
    echo "Swap file already exists, skipping"
fi

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

echo "Installing CloudWatch agent..."
CW_DEB=/tmp/amazon-cloudwatch-agent.deb
wget -q -O $CW_DEB https://s3.amazonaws.com/amazoncloudwatch-agent/ubuntu/amd64/latest/amazon-cloudwatch-agent.deb
sudo dpkg -i $CW_DEB
rm $CW_DEB

echo "Configuring CloudWatch agent (disk + memory metrics)..."
sudo tee /opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json > /dev/null <<'EOF'
{
  "metrics": {
    "append_dimensions": {
      "InstanceId": "${aws:InstanceId}"
    },
    "metrics_collected": {
      "disk": {
        "measurement": ["disk_used_percent"],
        "resources": ["/"],
        "metrics_collection_interval": 300
      },
      "mem": {
        "measurement": ["mem_used_percent"],
        "metrics_collection_interval": 300
      }
    }
  }
}
EOF

sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl \
  -a fetch-config \
  -m ec2 \
  -c file:/opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json \
  -s
echo "CloudWatch agent running"

echo "Configuring systemd journal log cap..."
sudo sed -i '/^SystemMaxUse=/d' /etc/systemd/journald.conf
echo "SystemMaxUse=100M" | sudo tee -a /etc/systemd/journald.conf > /dev/null
sudo systemctl restart systemd-journald
echo "Journal capped at 100MB"

echo "Configuring snap to retain only 2 revisions..."
sudo snap set system refresh.retain=2
echo "Snap revision retention set to 2"

echo "Setting up weekly apt autoremove..."
sudo tee /etc/cron.weekly/apt-autoremove > /dev/null <<'EOF'
#!/bin/bash
apt-get autoremove -y
apt-get clean
EOF
sudo chmod +x /etc/cron.weekly/apt-autoremove
echo "Weekly apt autoremove configured"

echo "Creating application directory..."
mkdir -p /home/ubuntu/eduquest-backend
cd /home/ubuntu/eduquest-backend

echo "Creating .env file..."
cat > .env <<'EOF'
APP_ENV=production

JWT_SECRET_KEY=prod-secret-key-CHANGE-THIS-TO-SECURE-KEY-DIFFERENT-FROM-DEV

API_GATEWAY_URL=https://ox6n5yri26.execute-api.us-east-2.amazonaws.com/prod

EOF

chmod 600 .env

echo "⚠️  IMPORTANT: Edit /home/ubuntu/eduquest-backend/.env with your actual PRODUCTION secret keys!"

echo "Creating systemd service..."
sudo tee /etc/systemd/system/eduquest-backend.service > /dev/null <<'EOF'
[Unit]
Description=EduQuest Backend FastAPI Application (prod)
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/eduquest-backend
Environment="PATH=/home/ubuntu/eduquest-backend/venv/bin:/usr/local/bin:/usr/bin:/bin"
Environment="APP_ENV=production"
EnvironmentFile=/home/ubuntu/eduquest-backend/.env
ExecStart=/home/ubuntu/eduquest-backend/venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=eduquest-backend

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload

echo "Configuring log rotation..."
sudo tee /etc/logrotate.d/eduquest-backend > /dev/null <<'EOF'
/home/ubuntu/eduquest-backend/*.log {
    daily
    rotate 7
    compress
    missingok
    notifempty
}
EOF
echo "Log rotation configured"

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
