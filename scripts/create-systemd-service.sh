#!/bin/bash

# Create systemd service for EduQuest Backend
# Run this script on the EC2 instance to set up the Flask application as a service

set -e

echo "Creating systemd service for EduQuest Backend..."

# Create service file
sudo tee /etc/systemd/system/eduquest-backend.service > /dev/null <<EOF
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

# Reload systemd
sudo systemctl daemon-reload

# Enable service to start on boot
sudo systemctl enable eduquest-backend

# Start service
sudo systemctl start eduquest-backend

# Check status
echo "Service status:"
sudo systemctl status eduquest-backend --no-pager

echo "=========================================="
echo "Service created successfully!"
echo "=========================================="
echo "Useful commands:"
echo "  sudo systemctl status eduquest-backend   - Check service status"
echo "  sudo systemctl restart eduquest-backend  - Restart service"
echo "  sudo systemctl stop eduquest-backend     - Stop service"
echo "  sudo systemctl start eduquest-backend    - Start service"
echo "  sudo journalctl -u eduquest-backend -f   - View logs"
