# scripts/

Runnable scripts for development, deployment, and scheduled jobs. Not collected by pytest.

All Python scripts are run from `eduquest-backend/` with the venv active:
```bash
source venv/bin/activate
python scripts/<script>.py
```

---

## Local dev

Tools and pipeline runners you execute on your machine.

| Script | What it does |
|--------|-------------|
| `check_arch.py` | Scans the codebase for architectural violations (router/service/DAO boundary breaches). Run before a PR. Lines marked `# arch-ok` are suppressed. |
| `check_s3.py` | Verifies S3 presigned-URL generation is working with your current credentials and bucket config. Run before deploying if you've touched S3 or AWS env vars. |
| `curriculum_pipeline.py` | Runs the full 5-stage curriculum pipeline: CoverageEvaluator → PerplexityService → PeriodScheduleAgent → quest entry building → HWAgent. Requires `OPENAI_API_KEY` and `PERPLEXITY_API_KEY`. `MOCK_AI=true` skips OpenAI calls; Perplexity still runs live. |
| `schedule_pipeline.py` | Runs stages 1–3 only: CoverageEvaluator → PerplexityService → PeriodScheduleAgent. Useful for testing schedule generation in isolation. `MOCK_AI=true` skips the PeriodScheduleAgent call. |

---

## Cron jobs

Run daily in production (e.g. via EC2 cron). Both are idempotent.

| Script | What it does |
|--------|-------------|
| `send_trial_reminders.py` | Sends trial-ending reminder emails to users whose trial is about to expire. Tracks sends via `membership.reminder_sent_at` to avoid duplicates. Run with `python -m scripts.send_trial_reminders`. |
| `snapshot_telemetry.py` | Pulls aggregate counts from Postgres and pushes them as PostHog person/group traits for analytics dashboards. Run with `python -m scripts.snapshot_telemetry`. |

---

## Infrastructure

All shell scripts. Require AWS CLI configured with appropriate credentials.

| Script | What it does |
|--------|-------------|
| `deploy-api-gateway.sh [prod\|dev]` | Deploys the API Gateway CloudFormation stack from `cloudformation/api-gateway.yaml`. Requires `cloudformation/parameters-<env>.json`. |
| `update-api-gateway.sh [prod\|dev]` | Re-deploys the API Gateway CloudFormation stack (same as deploy but for updates). |
| `delete-api-gateway.sh [prod\|dev]` | Deletes the API Gateway CloudFormation stack. Prompts for confirmation. |
| `deploy-to-ec2.sh <env> <instance-id>` | Packages the backend and deploys it to an EC2 instance via SSM. |
| `remote_deploy.sh` | Runs **on the EC2 instance** (not locally). Pulls latest from `production` branch, installs dependencies, writes the systemd service file, and restarts the server. |
| `deploy-s3.sh` | Deploys the S3 CloudFormation stack from `cloudformation/s3.yaml`. Requires `cloudformation/s3-parameters-prod.json` (copy from `s3-parameters-template.json`). For an existing bucket, use resource import — instructions are printed by the script. |
