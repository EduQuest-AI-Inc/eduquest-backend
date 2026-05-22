# CloudFormation

Version-controlled definition of EduQuest's AWS infrastructure. Every AWS resource managed here should exist in a template first — not created manually in the console.

## What this folder owns

| Template | Stack name (suggested) | What it creates |
|---|---|---|
| `ec2.yaml` | `eduquest-ec2` | Ubuntu 24.04 instance, IAM role (SSM), security group, systemd service definition, swap, log rotation |
| `s3.yaml` | `eduquest-s3` | Private uploads bucket with CORS policy for `eduquestai.org` and localhost dev origins |
| `api-gateway.yaml` | `eduquest-api-gateway` | REST API with HTTP proxy routes to EC2 for all backend path prefixes |
| `cloudwatch.yaml` | `eduquest-cloudwatch` | SNS alert topic, disk/memory/status-check alarms (requires CloudWatch agent on EC2) |

## What is NOT managed here

- **Supabase** — database, auth, RLS policies. Managed via Supabase dashboard and `supabase-auth-migration/`.
- **Vercel** — frontend deployment. Auto-deployed from `eduquest-frontend/` on push.
- **VPC / subnets / key pairs** — assumed to pre-exist. Pass IDs as parameters.

## Deploy order

Stacks are independent but `cloudwatch.yaml` requires the EC2 instance ID from `ec2.yaml`, and `api-gateway.yaml` requires the EC2 public IP. Deploy in this order:

1. `ec2.yaml` — note the `InstanceId` and `PublicIp` outputs
2. `s3.yaml` — independent, can deploy at any time
3. `api-gateway.yaml` — requires EC2 `PublicIp`
4. `cloudwatch.yaml` — requires EC2 `InstanceId`

## Parameter files

Each template has a corresponding `*-parameters-template.json` with placeholder values and a `*-prod.json` with the actual production values. Both are committed so the team has the current state.

| Template | Parameter file |
|---|---|
| `ec2.yaml` | `ec2-parameters-prod.json` |
| `s3.yaml` | `s3-parameters-prod.json` |
| `api-gateway.yaml` | `parameters-prod.json` |
| `cloudwatch.yaml` | *(pass parameters inline — see commands below)* |

## Deploy commands

All commands assume AWS CLI is configured with appropriate credentials and `us-east-1` region (or adjust `--region` accordingly).

**EC2:**
```bash
aws cloudformation deploy \
  --template-file ec2.yaml \
  --stack-name eduquest-ec2 \
  --parameter-overrides file://ec2-parameters-prod.json \
  --capabilities CAPABILITY_NAMED_IAM \
  --region us-east-1
```

**S3:**
```bash
aws cloudformation deploy \
  --template-file s3.yaml \
  --stack-name eduquest-s3 \
  --parameter-overrides file://s3-parameters-prod.json \
  --region us-east-1
```

**API Gateway** (update `parameters-prod.json` with current EC2 public IP first):
```bash
aws cloudformation deploy \
  --template-file api-gateway.yaml \
  --stack-name eduquest-api-gateway \
  --parameter-overrides file://parameters-prod.json \
  --region us-east-1
```

**CloudWatch** (requires CloudWatch agent installed and running on EC2):
```bash
aws cloudformation deploy \
  --template-file cloudwatch.yaml \
  --stack-name eduquest-cloudwatch \
  --parameter-overrides \
      InstanceId=i-YOURINSTANCEID \
      AlertEmail=your@email.com \
  --region us-east-1
```

## After deploying ec2.yaml

The template creates the instance and installs system dependencies, but does **not** deploy the application code. After the instance is up:

1. SSH in or use SSM Session Manager: `aws ssm start-session --target i-YOURINSTANCEID`
2. Clone the repo to `/home/ubuntu/eduquest-backend`
3. Create the virtualenv and install dependencies
4. Create `/home/ubuntu/eduquest-backend/.env` with production environment variables
5. Start the service: `sudo systemctl start eduquest-backend && sudo systemctl enable eduquest-backend`

## Updating a stack

Re-run the same `deploy` command with updated parameters or template. CloudFormation will compute a changeset and apply only the diff. For destructive changes (e.g. replacing the EC2 instance), review the changeset first:

```bash
aws cloudformation deploy ... --no-execute-changeset
aws cloudformation describe-change-set --stack-name eduquest-ec2 --change-set-name <name>
```

## Tags applied to all resources

| Tag | Value |
|---|---|
| `ManagedBy` | `cloudformation` |
| `Service` | `eduquest-backend` |
| `Environment` | `prod` |
