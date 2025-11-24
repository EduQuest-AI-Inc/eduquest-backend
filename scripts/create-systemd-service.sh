#!/bin/bash

set -e

echo "Creating systemd service for EduQuest Backend..."

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

sudo systemctl daemon-reload

sudo systemctl enable eduquest-backend

sudo systemctl start eduquest-backend

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
