# CLAUDE.md — Backend

See also: [data_access/CLAUDE.md](data_access/CLAUDE.md) for DAO and database patterns.

## Package Layout

```
eduquest-backend/
├── app.py                          # Flask app factory, Blueprint registration
├── main.py                         # Alternative FastAPI entry point (migration pending)
├── routes/                         # Feature modules (Blueprint + service files)
│   ├── auth/                       # routes.py, auth_service.py, password_reset_service.py, password_policy.py
│   ├── conversation/               # routes.py, conversation_service.py, grading_service.py,
│   │                               #   ltg_service.py, profile_service.py, teacher_feedback_service.py
│   ├── enrollment/                 # routes.py, enrollment_service.py
│   ├── period/                     # routes.py, period_service.py, period_enrollment_service.py,
│   │                               #   period_ltg_service.py, period_quest_service.py
│   ├── quest/                      # routes.py, quest_service.py, quest_creation_service.py,
│   │                               #   quest_retrieval_service.py, quest_grading_service.py
│   ├── teacher/                    # routes.py, teacher_service.py, period_schedule_service.py
│   ├── user/                       # routes.py, user_service.py
│   ├── waitlist/                   # routes.py, WaitlistService.py
│   ├── parent/                     # routes.py, parent_service.py
│   └── parent_waitlist/            # routes.py, parent_waitlist_service.py
├── models/                         # Pydantic domain models
│   ├── user.py                     # Base User model (shared fields: name, email, password, role, canvas)
│   ├── student.py                  # Student(User) — grade, strengths/weaknesses, tutorial status
│   ├── teacher.py                  # Teacher(User) — pilot_approved, school_id
│   └── parent.py                   # Parent(User) — linked_user_ids
├── bots/                           # All AI agent code (was EQ_agents/)
│   ├── agent.py                    # HWAgent — quest instruction/rubric generation
│   ├── grading_agent.py            # Multi-agent grading orchestrator
│   ├── ltg_agent.py                # Long-term goal agent
│   ├── guardrails.py               # Content safety guardrails
│   ├── profile_agent.py            # Student profile agent
│   ├── schedule_agent.py           # Schedule generation agent
│   ├── teacher_feedback_agent.py   # Teacher feedback agent
│   └── schemas/rubric.py           # Rubric Pydantic schema
├── services/                       # Cross-cutting business logic
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

Registered in app.py:

- `/conversation` — AI chat interactions with students
- `/auth` — Login, signup, Supabase integration
- `/user` — User profile and data management
- `/period` — Class period management
- `/teacher` — Teacher-specific operations
- `/enrollment` — Student-class enrollment
- `/quest` — Quest assignment and tracking
- `/pilot-waitlist` — Pilot waitlist management
- `/parent` — Parent homeschool class and invite management
- `/parent-waitlist` — Parent waitlist management

## Route Pattern

Each route module follows:

```
routes/[feature]/
  ├── routes.py              # Flask Blueprint and endpoints
  ├── [feature]_service.py   # Business logic (thin orchestrator)
  ├── [feature]_*_service.py # Sub-services for specific concerns
  └── __init__.py
```

Route handlers that do more than one distinct thing extract underscore-prefixed helpers in the same file (e.g. `_validate_pilot_access()`, `_resolve_identity()`, `_handle_file_submission()`). These are private to the module — no helper should exceed 20 lines.

## Error Handling

Custom exceptions in `exceptions/` are caught by global handlers in `app.py`:

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
python app.py
# http://0.0.0.0:5000, debug mode
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
