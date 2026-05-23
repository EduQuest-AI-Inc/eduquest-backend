#!/bin/bash
set -euo pipefail

log() { echo "[$(date '+%H:%M:%S')] $*"; }

trap 'log "FAILED at line $LINENO — exit code $?"' ERR

cd /home/ubuntu/eduquest-backend

log "--- Deploy started ---"
log "Current commit: $(git rev-parse HEAD) ($(git log -1 --format='%s'))"
OLD_COMMIT=$(git rev-parse HEAD)

log "Pulling latest changes..."
git clean -f
git pull origin production
NEW_COMMIT=$(git rev-parse HEAD)
log "Updated to: $NEW_COMMIT ($(git log -1 --format='%s'))"

if [ "$OLD_COMMIT" = "$NEW_COMMIT" ]; then
  log "WARNING: No new commits — deploying same code as before."
fi

log "Disk space before pip install:"
df -h /home/ubuntu
AVAIL_KB=$(df /home/ubuntu | awk 'NR==2 {print $4}')
if [ "$AVAIL_KB" -lt 512000 ]; then
  log "WARNING: Less than 500 MB free on /home/ubuntu ($((AVAIL_KB / 1024)) MB available). pip install may fail."
fi

log "Activating virtual environment..."
source venv/bin/activate
log "Installing dependencies..."
pip install -r requirements.txt

log "Verifying imports..."
venv/bin/python -c "import main; print('Import OK')"

log "Checking .env file exists..."
test -f /home/ubuntu/eduquest-backend/.env || { log "ERROR: .env file missing on EC2"; exit 1; }

log "Writing systemd service file..."
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
log "Restarting service..."
sudo systemctl restart eduquest-backend
log "Service status after restart:"
sudo systemctl status eduquest-backend --no-pager || true

log "Waiting for server to become healthy (up to 30s)..."
SERVER_READY=0
for i in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:8000/helloworld 2>/dev/null; then
    echo ""
    log "Server is healthy (after ${i}s)"
    SERVER_READY=1
    break
  fi

  if [ $((i % 10)) -eq 0 ]; then
    log "Still waiting (${i}s)... recent logs:"
    sudo journalctl -u eduquest-backend -n 10 --no-pager || true
  fi

  sleep 1
done

if [ "$SERVER_READY" != "1" ]; then
  log "Health check failed after 30s — collecting diagnostics..."
  echo ""
  echo "--- Port 8000 listeners ---"
  ss -tlnp | grep 8000 || echo "(nothing listening on 8000)"
  echo ""
  echo "--- systemctl status ---"
  sudo systemctl status eduquest-backend --no-pager || true
  echo ""
  echo "--- journalctl (last 50 lines) ---"
  sudo journalctl -u eduquest-backend -n 50 --no-pager || true
  echo ""

  log "Rolling back to $OLD_COMMIT..."
  git reset --hard "$OLD_COMMIT"
  pip install -r requirements.txt
  sudo systemctl restart eduquest-backend

  log "Verifying rollback health..."
  ROLLBACK_READY=0
  for i in $(seq 1 15); do
    if curl -fsS http://127.0.0.1:8000/helloworld 2>/dev/null; then
      echo ""
      log "Rollback is healthy."
      ROLLBACK_READY=1
      break
    fi
    sleep 1
  done

  if [ "$ROLLBACK_READY" != "1" ]; then
    log "ERROR: Rollback health check also failed — service may be down."
    sudo journalctl -u eduquest-backend -n 30 --no-pager || true
  fi

  log "Deploy FAILED. Rolled back to $OLD_COMMIT."
  exit 1
fi

log "Deploy complete. Running commit: $NEW_COMMIT"
