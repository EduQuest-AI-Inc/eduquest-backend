# DynamoDB Removal Checklist

## Before Starting

- [ ] Confirm `USE_SUPABASE=true` is set in the production environment
- [ ] Confirm prod has been running cleanly on Supabase for a while (no DynamoDB traffic)
- [ ] Back up any DynamoDB tables you haven't 100% confirmed are fully migrated

## Code to Delete

- [ ] All `data_access/*_dao.py` files (the non-Supabase ones — keep `data_access/supabase/`)
- [ ] `data_access/config.py` — the boto3 DynamoDB config
- [ ] `data_access/base_dao.py` — the DynamoDB base DAO (keep `data_access/supabase/base_dao.py`)

## Code to Update

- [ ] `app.py` — remove the `USE_SUPABASE` conditional DAO switching; always import from `data_access/supabase/`
- [ ] `requirements.txt` — **do NOT remove boto3** — still needed for S3 (`services/s3_service.py`) and SES (`services/email_service.py`)

## Infrastructure

- [ ] Decommission CloudFormation stacks in `cloudformation/` (tear down the actual AWS DynamoDB tables)
- [ ] Do this **last**, after code is deployed and confirmed working

## Tests

- [ ] Check `tests/` for any DynamoDB mocks or fixtures and update them to use Supabase
