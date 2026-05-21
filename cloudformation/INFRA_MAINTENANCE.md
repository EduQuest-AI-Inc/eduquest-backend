# EduQuest Backend Infrastructure Maintenance

Checklist of improvements to make the EC2 instance stable, organized, and maintainable.
Items are roughly in priority order.

---

## Done (May 2026)
- [x] Assigned Elastic IP `16.58.29.145` — public IP no longer changes on stop/start
- [x] Created swap file (1.2 GiB) — prevents OOM crashes
- [x] Expanded root EBS volume from 8 GiB → 20 GiB
- [x] Added `ec2.yaml` CloudFormation template for the instance
- [x] Updated `ec2-parameters-prod.json` with real KeyPairName, VpcId, SubnetId
- [x] Updated `parameters-prod.json` EC2PublicIP to Elastic IP `16.58.29.145`

---

## High Priority

### 1. Update CloudFormation parameter files with real values
`ec2-parameters-prod.json` still has placeholder values. Fill in:
- `KeyPairName` — your actual EC2 key pair name
- `VpcId` — `vpc-04da0fb2c6d375e10` (visible on instance details page)
- `SubnetId` — `subnet-030d2cbe175223a42` (visible on instance details page)

### ~~2. Remove API Gateway and route all traffic through nginx~~ ✓ DONE
API Gateway is redundant — nginx on the EC2 does the same job for free with less latency.
The live stack (`eduquest-api-gateway-prod`) can be deleted once Vercel points at the nginx domain.

Steps (do in order):
1. **Verify nginx has SSL** — SSH in and check `sudo nginx -T | grep ssl_certificate`. If no cert, run:
   ```bash
   sudo apt install -y certbot python3-certbot-nginx
   sudo certbot --nginx -d api.eduquestai.org
   ```
2. **Update Vercel env var** `AGENT_SERVICE_URL` — change from `http://16.58.29.145:5000` to `https://api.eduquestai.org`
3. **Smoke-test** — confirm the frontend can reach the backend through the new URL
4. **Delete the CloudFormation stack** — in AWS Console: CloudFormation → `eduquest-api-gateway-prod` → Delete
5. **Archive `api-gateway.yaml`** — keep it in the repo for reference but it no longer needs to be deployed

### ~~3. Migrate from port 5000 → 8000~~ ✓ DONE
The live server runs on port 5000 (leftover from Flask). All three of these must be changed together:

1. **nginx** (`/etc/nginx/sites-available/eduquest`) — change `proxy_pass http://127.0.0.1:5000` → `proxy_pass http://127.0.0.1:8000`
2. **systemd service** (`/etc/systemd/system/eduquest-backend.service`) — update the uvicorn bind port to `8000`
3. **Confirm Vercel** `AGENT_SERVICE_URL` points to `https://api.eduquestai.org` (no port needed after item 2 above)

After updating nginx and the systemd service:
```bash
sudo systemctl daemon-reload
sudo systemctl restart eduquest-backend
sudo systemctl restart nginx
```

### ~~4. Update parameters-prod.json with the Elastic IP~~ ✓ DONE
`EC2PublicIP` is already `16.58.29.145` in `parameters-prod.json`.

### ~~5. Add CloudWatch alarms~~ ✓ DONE
`cloudwatch.yaml` CloudFormation template created with three alarms:
- **Disk > 80%** — SNS email alert (CWAgent metric — requires agent on instance)
- **Memory > 85%** — SNS email alert (CWAgent metric — requires agent on instance)
- **StatusCheckFailed** — built-in EC2 metric, no agent needed

To deploy:
```bash
aws cloudformation deploy \
  --template-file cloudformation/cloudwatch.yaml \
  --stack-name eduquest-cloudwatch-prod \
  --parameter-overrides \
    InstanceId=<your-instance-id> \
    AlertEmail=<your-email>
```

To install the CloudWatch agent on the instance (required for disk + memory alarms):
```bash
sudo apt install -y amazon-cloudwatch-agent
# Then configure via /opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json
```

### 6. Check systemd service has auto-restart configured
Verify the service restarts automatically if uvicorn crashes:
```bash
sudo systemctl cat eduquest-backend
```
It should contain `Restart=always` and `RestartSec=5`. If not, edit
`/etc/systemd/system/eduquest-backend.service` and add those lines under `[Service]`.

---

## Medium Priority

### ~~7. Run pending package updates~~ ✓ DONE

### ~~8. Enable automatic security updates~~ ✓ DONE

### 9. Set up EBS snapshots
No backups are currently configured (Snapshot summary shows 0/2 volumes backed up).
Go to EC2 > Lifecycle Manager > Create snapshot policy for `vol-088ee0d6fc2f364cc`:
- Daily snapshots, retain 7 days
- This protects against data loss if the volume corrupts

### 10. Consider upgrading from t2.micro to t3.small
t2.micro has 1 GiB RAM. Running FastAPI + OpenAI agents is tight even with swap.
t3.small (2 GiB RAM, ~$15/mo) would eliminate most OOM risk without swap being a crutch.
To upgrade: stop instance → Actions > Instance settings > Change instance type → start.

### ~~11. Move `setup-prod-instance.sh` config into `ec2.yaml` UserData~~ ✓ DONE
All five items are now in the `UserData` block in `ec2.yaml`:
- systemd journal cap (`SystemMaxUse=100M` in `/etc/systemd/journald.conf`)
- snap revision retention (`snap set system refresh.retain=2`)
- weekly apt autoremove cron (`/etc/cron.weekly/apt-autoremove`)
- full systemd service file (`/etc/systemd/system/eduquest-backend.service`)
- app directory creation (`mkdir -p /home/ubuntu/eduquest-backend`)

A CloudFormation-provisioned instance is now self-contained; `setup-prod-instance.sh` is still useful for manual runs but is no longer the only source of truth.

### ~~12. Fix `deploy-to-ec2.sh` to install into venv, not system Python~~ ✓ DONE
`scripts/deploy-to-ec2.sh` now creates the venv and installs via the venv pip, matching
the path the systemd service uses (`/home/ubuntu/eduquest-backend/venv/bin/python`).

---

## Low Priority / Nice to Have

### ~~14. Add log rotation for the backend app~~ ✓ DONE
`/etc/logrotate.d/eduquest-backend` added to `ec2.yaml` UserData and `setup-prod-instance.sh`.
Rotates any `*.log` files in `/home/ubuntu/eduquest-backend/` daily, keeps 7 compressed copies.
`missingok`/`notifempty` make it a no-op if the app never writes log files (uvicorn logs to journal).

### ~~15. Increase swap to 2 GiB~~ ✓ DONE
`ec2.yaml` already provisions 2 GiB swap (`SwapSizeGB` default = 2). `setup-prod-instance.sh` updated to match.
**Live instance still has 1.2 GiB** — run these once to expand it:
```bash
sudo swapoff /swapfile
sudo fallocate -l 2G /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
free -h  # verify 2.0G swap
```

### ~~16. Tag the EC2 instance properly~~ ✓ DONE
Tags added to `BackendInstance` in `ec2.yaml`: `Environment=prod`, `Service=eduquest-backend`, `ManagedBy=cloudformation`.
**Live instance:** add these in the AWS Console (EC2 → instance → Tags) or via CLI until the stack is redeployed.
