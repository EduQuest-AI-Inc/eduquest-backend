# eduquest-backend

For architecture, API reference, environment variables, and development conventions, see [CLAUDE.md](CLAUDE.md).

## Prerequisites

- **Python 3.11+** — `python3 --version`
- `make setup` handles everything else (venv creation, dependency install, git hook install)

## Setup

```bash
cd eduquest-backend
make setup          # creates venv, installs all deps, installs pre-commit + pre-push hooks
source venv/bin/activate
```

`make setup` installs two git hook stages:
- **pre-commit:** ruff lint, OpenAPI schema export (when routers change)
- **pre-push:** architecture lint, pyright, unit test suite

## Environment

```bash
cp .env.example .env
```

Minimum secrets needed for local development — ask the team lead for values:

| Variable | Purpose |
|---|---|
| `JWT_SECRET_KEY` | Must match the frontend value exactly |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase admin key (server-side only) |
| `SUPABASE_ANON_KEY` | Supabase public key |
| `SUPABASE_JWT_SECRET` | Used to verify Supabase-issued JWTs |
| `OPENAI_API_KEY` | Required for AI features |

All other keys (Stripe, AWS/S3, SES, Perplexity, Gemini) are only needed when working on those specific features.

**Local dev tip:** uncomment `MOCK_AI=true` in your `.env` to run the server without making real OpenAI/Gemini/Perplexity API calls. All AI responses will be fast stubs — useful when working on non-AI features.

## Run

```bash
uvicorn main:app --reload
# http://localhost:8000
```

## Test

```bash
# Unit tests (fully offline — no .env needed):
venv/bin/pytest tests/unit/ -m unit

# Integration tests (require live Supabase — needs .env):
venv/bin/pytest -m integration
```

See [CLAUDE.md](CLAUDE.md) for the full test command reference and coverage options.
