# CLAUDE.md — Backend

See also: [data_access/CLAUDE.md](data_access/CLAUDE.md) for DAO and database patterns.

## Package Layout

```
eduquest-backend/
├── main.py                         # FastAPI app factory and entry point (sole server — Flask migration complete)
├── api/                            # FastAPI layer
│   ├── deps.py                     # get_auth() dependency → AuthPayload (JWT from header or cookie)
│   └── routers/
│       ├── auth.py                 # /auth — login, register, password reset
│       ├── conversation.py         # /conversation — profile assistant, update assistant
│       ├── enrollment.py           # /enrollment — enroll/unenroll students
│       ├── parent.py               # /parent — parent invite, child lookup
│       ├── period.py               # /period — LTG conversation, homework agent
│       ├── quest.py                # /quest — quest retrieval, submission
│       ├── teacher.py              # /teacher — Canvas courses (teacher-only)
│       ├── user.py                 # /user — user profile
│       └── waitlist.py             # /pilot-waitlist — status, join
├── services/                         # Service/business logic layer (imported by api/routers/)
│   ├── auth_utils.py               # Shared auth helpers used across service modules
│   ├── auth/                       # auth_service.py, password_reset_service.py, password_policy.py
│   ├── conversation/               # conversation_service.py, grading_service.py,
│   │                               #   ltg_service.py, profile_service.py, teacher_feedback_service.py
│   ├── enrollment/                 # enrollment_service.py
│   ├── period/                     # period_service.py, period_enrollment_service.py,
│   │                               #   period_quest_service.py, period_schedule_service.py,
│   │                               #   period_management_service.py, period_file_helpers.py
│   ├── quest/                      # quest_service.py, quest_creation_service.py,
│   │                               #   quest_retrieval_service.py, quest_grading_service.py
│   ├── teacher/                    # teacher_service.py, period_schedule_service.py
│   ├── user/                       # user_service.py
│   ├── waitlist/                   # WaitlistService.py
│   └── parent/                     # parent_service.py
├── models/                         # Pydantic domain models
│   ├── user.py                     # Base User model
│   ├── student.py                  # Student(User)
│   ├── teacher.py                  # Teacher(User)
│   ├── parent.py                   # Parent(User)
│   ├── student_long_term_goal.py   # StudentLongTermGoal — one goal per (user_id, period_id)
│   ├── quest.py                    # Quest — assignment with rubric, grade, status
│   ├── enrollment.py               # Enrollment — student ↔ period membership
│   ├── period.py                   # Period — class with vector store and Canvas metadata
│   ├── period_schedule.py          # PeriodSchedule — AI-generated weekly schedule
│   ├── conversation.py             # Conversation — chat session record
│   ├── session.py                  # Session — JWT session record
│   ├── parent_invite.py            # ParentInvite — invite token for parent signup
│   └── password_reset_token.py     # PasswordResetToken — reset link token
├── bots/                           # All AI agent code (was EQ_agents/)
│   ├── agent.py                    # HWAgent — quest instruction/rubric generation
│   ├── grading_agent.py            # Multi-agent grading orchestrator
│   ├── ltg_agent.py                # Long-term goal agent
│   ├── guardrails.py               # Content safety guardrails
│   ├── profile_agent.py            # Student profile agent
│   ├── schedule_agent.py           # Schedule generation agent
│   ├── teacher_feedback_agent.py   # Teacher feedback agent
│   ├── ltg_conversation_service.py # Re-export shim (backwards compat for old imports)
│   └── schemas/rubric.py           # Rubric Pydantic schema
├── integrations/                   # External service adapters (shared across features)
│   ├── s3_service.py               # AWS S3 upload helpers
│   ├── canvas_service.py           # Canvas LMS integration (canvasapi library)
│   └── email_service.py            # SES email sending
├── utils/
│   ├── conversion_utils.py         # convert_decimals() for DynamoDB Decimal→float
│   ├── token_utils.py              # extract_auth_token(), get_user_id_from_token(), set_auth_cookie()
│   └── validation_utils.py         # get_client_ip(request), normalize_email(email)
├── exceptions/                     # Custom exception classes → global HTTP status mappings
│   ├── auth_error.py               # → 401
│   ├── not_found_error.py          # → 404
│   └── validation_error.py         # → 400
├── constants/
│   └── timeouts.py                 # JWT_EXPIRY_HOURS, INVITE_EXPIRY_HOURS
└── tests/
```

## API Modules

### FastAPI (`main.py`) — sole server

- `/auth` — login, register, password reset
- `/conversation` — profile assistant, update assistant
- `/enrollment` — student enrollment
- `/parent` — parent invite and child lookup
- `/period` — LTG conversation, homework agent, period schedule CRUD (teacher + parent)
- `/quest` — quest retrieval, submission
- `/teacher` — Canvas courses (teacher-only)
- `/user` — user profile
- `/pilot-waitlist` — status, join

## Route Pattern

FastAPI routers live in `api/routers/[feature].py`. Each imports service classes from `services/[feature]/`:

```
api/routers/[feature].py       # FastAPI router — HTTP boundary only
services/[feature]/
  ├── [feature]_service.py     # Business logic (thin orchestrator)
  ├── [feature]_*_service.py   # Sub-services for specific concerns
  └── __init__.py
```

Router handlers that do more than one distinct thing extract underscore-prefixed helpers in the same file (e.g. `_validate_pilot_access()`, `_resolve_identity()`, `_handle_file_submission()`). These are private to the module — no helper should exceed 20 lines.

## Error Handling

Custom exceptions in `exceptions/` are caught by global handlers in `main.py`:

- `ValidationError` → 400
- `NotFoundError` → 404
- `AuthError` → 401

Route handlers raise these exceptions — do **not** add `except` clauses for them in route code.

## Auth Token Utilities

`utils/token_utils.py`:

- `extract_auth_token(request)` — reads Bearer header with cookie fallback
- `get_user_id_from_token(auth_token, session_dao)` — validates token, returns `user_id`, raises `AuthError` on failure
- `set_auth_cookie(response, token)` — sets `auth_token` cookie with environment-appropriate flags

## Constants

`constants/timeouts.py`:

- `JWT_EXPIRY_HOURS = 1` — JWT token lifetime
- `INVITE_EXPIRY_HOURS = 24` — parent invite expiry

## Agent System

All agent code in `bots/` (not `EQ_agents/` — that directory no longer exists). Agents use OpenAI's Agents SDK (`from agents import Agent, Runner`).

- `bots/grading_agent.py` (`GradingOrchestrator`) — produces per-skill float scores (0.0–1.0). The frontend reads aggregated skill metrics from the Supabase `aggregated_metrics` table directly.

## Development

**Setup** (always use venv):

```bash
cd eduquest-backend
source venv/bin/activate
pip install -r requirements.txt
```

**Environment** — `.env` file:

- `JWT_SECRET_KEY`
- `AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`
- `OPENAI_API_KEY`
- `API_GATEWAY_URL` (optional)
- `USE_SUPABASE=true` to enable Supabase DAOs

**Run**:

```bash
uvicorn main:app --reload
# http://0.0.0.0:8000
```

**Testing**:

```bash
pytest
pytest -m unit
pytest -m integration
pytest -m auth
pytest tests/test_teacher_dao.py
pytest --cov=. --cov-report=html
```

Configuration in [pytest.ini](pytest.ini). Markers: unit, integration, auth, api, smoke, slow.
