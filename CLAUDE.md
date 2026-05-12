# CLAUDE.md — Backend

See also: [data_access/CLAUDE.md](data_access/CLAUDE.md) for DAO and database patterns.
See also: [ARCH_DECISIONS.md](ARCH_DECISIONS.md) for authoritative decisions on router boundaries, auth enforcement, enrollment checks, agent instantiation, service dependencies, and testing conventions.

## Package Layout

```
eduquest-backend/
├── main.py                         # FastAPI app factory and entry point (sole server — Flask migration complete)
├── routers/                        # FastAPI layer
│   ├── deps.py                     # require_roles(...) dependency → AuthPayload (JWT from header or cookie)
│   ├── auth.py                     # /auth — login, signup (with trial_confirmed for parent/teacher), password reset
│   ├── billing.py                  # /billing — membership status, Stripe checkout/portal, webhook
│   ├── conversation.py             # /conversation — profile assistant, update assistant
│   ├── curriculum.py               # /curriculum — per-period curriculum generation/approval
│   ├── enrollment.py               # /enrollment — enroll/unenroll students
│   ├── ltg.py                      # /period — LTG conversation routes (mounted under /period)
│   ├── parent.py                   # /parent — parent invite, child lookup
│   ├── period.py                   # /period — period CRUD, homework agent, file uploads
│   ├── quest.py                    # /quest — quest retrieval, submission
│   ├── teacher.py                  # /teacher — Canvas courses, skill-mastery analytics
│   ├── user.py                     # /user — user profile, tutorial state
│   └── waitlist.py                 # /pilot-waitlist — status, join
├── services/                         # Service/business logic layer (imported by routers/)
│   ├── auth/                       # auth_service.py, password_reset_service.py, password_policy.py
│   ├── billing/                    # membership_service.py (trial lifecycle, plan limits,
│   │                               #   Stripe sync), trial_reminder_service.py
│   ├── conversation/               # conversation_service.py, grading_service.py,
│   │                               #   ltg_service.py, profile_service.py, teacher_feedback_service.py
│   ├── curriculum/                 # curriculum_service.py
│   ├── enrollment/                 # enrollment_service.py (CRUD, verify_and_enroll, unenroll,
│   │                               #   get_my_periods, assert_enrolled)
│   ├── knowledge_graph/            # knowledge_graph_service.py, curriculum_parser.py
│   ├── period/                     # period_service.py, period_quest_service.py,
│   │                               #   period_management_service.py, period_file_service.py
│   ├── quest/                      # quest_service.py, quest_creation_service.py,
│   │                               #   quest_retrieval_service.py, quest_grading_service.py
│   ├── tracking/                   # PostHog server-side analytics (posthog_client.py,
│   │                               #   events.py, track.py)
│   ├── user/                       # user_service.py
│   ├── waitlist/                   # waitlist_service.py
│   └── parent/                     # parent_service.py
├── models/                         # Pydantic domain models
│   ├── user.py                     # Base User model
│   ├── student.py                  # Student(User)
│   ├── teacher.py                  # Teacher(User)
│   ├── parent.py                   # Parent(User)
│   ├── membership.py               # Membership — parent/teacher billing record
│   │                               #   NOTE: created_at + updated_at use default_factory
│   │                               #   because Supabase enforces NOT NULL on updated_at
│   ├── student_long_term_goal.py   # StudentLongTermGoal — one goal per (user_id, period_id)
│   ├── student_skill_mastery.py    # MASTERY_CUTOFF (0.70) for boolean mastery
│   ├── quest.py                    # Quest — assignment with rubric, grade, status
│   ├── enrollment.py               # Enrollment — student ↔ period membership
│   ├── period.py                   # Period — class with vector store and Canvas metadata
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
│   ├── provider.py                 # Bot provider — factory for real and mock bot instances
│   ├── teacher_feedback_agent.py   # Teacher feedback agent
│   ├── _mocks.py                   # Mock bot instances for testing
│   └── schemas/rubric.py           # Rubric Pydantic schema
├── integrations/                   # External service adapters (shared across features)
│   ├── s3_service.py               # AWS S3 upload helpers
│   ├── canvas_service.py           # Canvas LMS integration (canvasapi library)
│   ├── perplexity_service.py       # Perplexity Agent API (deep-research preset) for curriculum research
│   ├── stripe_service.py           # Stripe customer/subscription helpers, webhook signature
│   └── email_service.py            # SES email sending
├── utils/
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

- `/auth` — login, signup (`trial_confirmed: true` is required for parent/teacher), password reset
- `/billing` — `GET /membership`, `POST /checkout-session`, `POST /portal-session`, `POST /webhook`
- `/conversation` — profile assistant, update assistant
- `/curriculum` — curriculum generation/approval per period
- `/enrollment` — student enrollment
- `/parent` — parent invite and child lookup
- `/period` — period CRUD, homework agent; also the prefix for `ltg.py` (LTG conversation), which is a separate router file mounted under `/period`
- `/quest` — quest retrieval, submission
- `/teacher` — Canvas courses, skill-mastery analytics
- `/user` — user profile, tutorial state
- `/pilot-waitlist` — status, join

## Membership / Trial Lifecycle

`MembershipService` (`services/billing/membership_service.py`) is the only seam that creates and reads memberships:

- `start_trial_if_eligible(user_id, role)` — idempotent; creates a `trialing` row valid for `TRIAL_DAYS = 30` (no card collected). Called from both `routers/auth.py:signup` and `routers/auth.py:login` (the login call is a backfill for legacy accounts).
- `evaluate_access(user_id, role) → MembershipAccess` — used by `assert_can_create_class` / `assert_can_add_student_to_period`. Self-heals expired trials (status flips to `expired`).
- `apply_stripe_subscription(subscription)` — invoked from the `/billing/webhook` handler on `customer.subscription.*` and `checkout.session.completed`.

Both auth handlers wrap the trial call in `try/except` so signup/login never fail because of billing. Because of that, **bugs in `start_trial_if_eligible` are silent**: when debugging a "missing trial" report, instrument inside the service and inspect the swallowed exception. A real example we hit: `Membership.updated_at` was `Optional[str] = None`, which `to_item()` serialized to `null`, violating the Supabase `NOT NULL` constraint with PostgREST error code `23502`. Fix: give `updated_at` the same `default_factory` as `created_at` in `models/membership.py`.

## Route Pattern

FastAPI routers live in `routers/[feature].py`. Each imports service classes from `services/[feature]/`:

```
routers/[feature].py       # FastAPI router — HTTP boundary only
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
- bare `Exception` → 500 (catch-all; logs full traceback)

**Rule: route handlers must never catch bare `Exception` to convert it to a 500.** All unhandled exceptions bubble up to the global handler, which owns the 500 mapping. This keeps logging, error shape, and observability consistent across every route.

The only `except` clauses that belong in route handlers are intentional HTTP-branch mappings (e.g. `except MembershipRequiredError → 403`, `except ValueError → 400`) or intentional swallows where a sub-operation must not block the primary flow (e.g. billing trial-start during login — marked with a `# must not block <action>` comment).

Handlers that must perform cleanup before propagating (e.g. `shutil.rmtree` on a temp dir) should do so and then `raise` the original exception — never convert it to `HTTPException(500)`.

**Service guard methods must not use an `assert_` prefix.** Python's `unittest.mock` treats any attribute starting with `assert_` as a potential misspelled assertion helper and raises `AttributeError` at test time. Use `check_*` or `verify_*` instead (e.g. `check_enrolled`, `check_can_create_class`).

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

- `bots/grading_agent.py` (`GradingOrchestrator`) — produces per-skill float scores (0.0–1.0). Results are written to `aggregated_metrics` via `AggregatedMetricsDAO`.
- `bots/schedule_agent.py` (`PeriodScheduleAgent`) — generates Week→Lesson→Concept→Skill schedule hierarchy. Accepts `research_context` (from Perplexity) to fill curriculum gaps when no files are uploaded.
- `bots/coverage_evaluator.py` (`CoverageEvaluator`) — single `gpt-4o-mini` structured call; returns `sufficient`, `gaps`, and `research_queries`. Used before schedule generation to decide whether to call Perplexity.
- `integrations/perplexity_service.py` (`PerplexityService`) — calls `POST https://api.perplexity.ai/v1/agent` with `{"preset": "deep-research", "input": ...}` via `httpx`. Response text is in `output[-1]["content"][0]["text"]` (last item of type "message" in the `output` array). NOT the OpenAI-compatible `/chat/completions` endpoint.

## Slideshow / PPTX Pipeline

The PPTX feature generates PowerPoint decks per lesson. Unlike the conversation agents (which use a stateful `OpenAIConversationsSession`), the slideshow pipeline is **stateless** — each generation is a fresh `Runner.run()` call with `max_turns=80`.

**Agent chain:** `PptxAgent → OrchestratorAgent → ContentWriterAgent / VisualReviewAgent / SLIDE_TOOLS`

- `bots/slideshow/pptx_agent.py` (`PptxAgent`) — top-level entry point; calls `OrchestratorAgent().run_async()`, then renders the resulting `CompleteSlideDeck` to `.pptx` (via `utils/rendering/pptx_renderer.py`) and HTML (via `utils/rendering/html_renderer.py`). Returns `{"pptx_bytes": bytes, "html_str": str}`.
- `bots/slideshow/orchestrator_agent.py` (`OrchestratorAgent`) — triage agent; designs the deck and calls specialist sub-agents via `SLIDE_TOOLS` function tools. Returns a `CompleteSlideDeck`.
- `bots/slideshow/content_writer_agent.py` (`ContentWriterAgent`) — writes `title`, `bullets`, and `speaker_notes` for one slide.
- `bots/slideshow/visual_review_agent.py` (`VisualReviewAgent`) — reviews generated images; returns `approved`, `regenerate`, or `flag`.
- `bots/tools/` — `SLIDE_TOOLS` are `@function_tool` wrappers registered to the orchestrator: `content_tool`, `image_tool`, `chart_tool`, `review_tool`, `html_tool`.

**Status lifecycle:** `LessonPptx` rows transition `pending → generating → done | failed`. Managed by `services/slides/pptx_generation_service.py` (`PptxGenerationService`).

**Mock:** `MockPptxAgent` lives in `bots/_mocks.py` alongside the other mocks. It generates a minimal real `.pptx` file using `python-pptx` and returns non-empty `html_str` so the HTML upload branch is exercised. `MockBotProvider.create_pptx_agent()` returns it.

## Development

**Setup** (always use venv):

```bash
cd eduquest-backend
source venv/bin/activate
pip install -r requirements.txt
```

**Environment** — `.env` file:

- `JWT_SECRET_KEY` — must match the frontend value exactly so cookies issued by either side verify on the other
- `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`
- `OPENAI_API_KEY`
- `PERPLEXITY_API_KEY` — required for `PerplexityService` (Perplexity Agent API)
- `AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` — S3 uploads + SES email
- `SES_FROM_EMAIL`, `FRONTEND_BASE_URL` — password reset emails, Stripe redirect URLs
- `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` — Stripe API + webhook signature
- `STRIPE_PRICE_STARTER`, `STRIPE_PRICE_GROWTH`, `STRIPE_PRICE_PRO` — Stripe price IDs for each plan
- `PILOT_WAITLIST_ENABLED` (optional; default `true`)
- `API_GATEWAY_URL` (optional)

**Run**:

```bash
uvicorn main:app --reload
# http://0.0.0.0:8000
```

**Testing**:

```bash
# Load .env before running one-off Python tests (venv doesn't auto-load it):
set -a && source .env && set +a && python -c "..."

# All pytest runs fail with ModuleNotFoundError: No module named 'supabase' in local dev
# — supabase is not installed in the venv. Tests requiring DAO access cannot be run locally.
# Use standalone python -c scripts for agent/integration layer testing.

pytest
pytest -m unit
pytest -m integration
pytest -m auth
pytest tests/test_teacher_dao.py
pytest --cov=. --cov-report=html
```

Configuration in [pytest.ini](pytest.ini). Markers: unit, integration, auth, api, smoke, slow.
