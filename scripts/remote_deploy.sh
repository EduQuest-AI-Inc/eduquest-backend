#!/bin/bash
set -e

cd /home/ubuntu/eduquest-backend

echo "Saving rollback point..."
OLD_COMMIT=$(git rev-parse HEAD)

echo "Pulling latest changes..."
git clean -f
git pull origin production

echo "Activating virtual environment..."
source venv/bin/activate
pip install -r requirements.txt

echo "Verifying imports..."
venv/bin/python -c "import main; print('Import OK')"

echo "Checking .env file exists..."
test -f /home/ubuntu/eduquest-backend/.env || { echo "ERROR: .env file missing on EC2"; exit 1; }

echo "Writing systemd service file..."
{
  echo '[Unit]'
  echo 'Description=EduQuest Backend'
  echo 'After=network.target'
  echo ''
  echo '[Service]'
  echo 'User=ubuntu'
  echo 'WorkingDirectory=/home/ubuntu/eduquest-backend'
  echo 'EnvironmentFile=/home/ubuntu/eduquest-backend/.env'
  echo 'ExecStart=/home/ubuntu/eduquest-backend/venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8000'
  echo 'Restart=on-failure'
  echo 'RestartSec=3'
  echo ''
  echo '[Install]'
  echo 'WantedBy=multi-user.target'
} | sudo tee /etc/systemd/system/eduquest-backend.service > /dev/null

sudo systemctl daemon-reload
sudo systemctl enable eduquest-backend || true
echo "Restarting service..."
sudo systemctl restart eduquest-backend

echo "Waiting for server..."
SERVER_READY=0
for i in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:8000/helloworld 2>/dev/null; then
    echo ""
    echo "Server is healthy"
    SERVER_READY=1
    break
  fi
  sleep 1
done

if [ "$SERVER_READY" != "1" ]; then
  echo "Health check failed — rolling back to $OLD_COMMIT..."
  git reset --hard "$OLD_COMMIT"
  pip install -r requirements.txt
  sudo systemctl restart eduquest-backend
  echo "Rollback complete. Deploy failed."
  echo "--- journalctl (failed deploy) ---"
  sudo journalctl -u eduquest-backend -n 50 --no-pager || true
  exit 1
fi

echo "Deploy complete."
