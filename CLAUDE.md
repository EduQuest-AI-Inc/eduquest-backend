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
│   ├── lessons.py                  # /lessons — presigned URLs for lesson PPTX and HTML
│   ├── ltg.py                      # /period — LTG conversation routes (mounted under /period)
│   ├── parent.py                   # /parent — parent invite, child lookup
│   ├── period.py                   # /period — period CRUD, homework agent, file uploads
│   ├── quest.py                    # /quest — quest retrieval, submission
│   ├── slides.py                   # /slides — PPTX status by period, restart generation
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
│   ├── knowledge_graph/            # knowledge_graph_service.py
│   ├── period/                     # period_service.py, period_quest_service.py,
│   │                               #   period_management_service.py, period_file_service.py
│   ├── quest/                      # quest_service.py, quest_creation_service.py,
│   │                               #   quest_retrieval_service.py, quest_grading_service.py
│   ├── tracking/                   # PostHog server-side analytics (posthog_client.py,
│   │                               #   events.py, track.py)
│   ├── user/                       # user_service.py
│   ├── waitlist/                   # waitlist_service.py
│   ├── parent/                     # parent_service.py
│   └── slides/                     # pptx_generation_service.py — status lifecycle (pending→generating→done|failed), restart_batch
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
├── bots/                           # All AI agent code (subdirectory-organized)
│   ├── grading_agent.py            # Multi-agent grading orchestrator
│   ├── ltg_agent.py                # Long-term goal agent
│   ├── guardrails.py               # Content safety guardrails
│   ├── profile_agent.py            # Student profile agent
│   ├── protocol.py                 # BotProviderProtocol, PptxAgentProtocol
│   ├── provider.py                 # BotProvider factory for real and mock instances
│   ├── teacher_feedback_agent.py   # Teacher feedback agent
│   ├── _mocks.py                   # MockBotProvider and mock agents for testing
│   ├── curriculum/                 # curriculum_agent.py (Week→Lesson→Concept→Skill),
│   │                               #   coverage_evaluator.py (decides Perplexity research)
│   ├── quests/                     # quest_agent.py (HWAgent — instructions/rubric),
│   │                               #   ltg_schedule_agent.py (LTG → per-week quest names)
│   ├── schemas/                    # rubric.py, instructions.py, curriculum.py
│   ├── slideshow/                  # pptx_agent.py, orchestrator_agent.py,
│   │                               #   content_writer_agent.py, visual_review_agent.py
│   └── tools/                      # @function_tool wrappers: content, image, chart,
│                                   #   review, html, knowledge_graph_tools
├── integrations/                   # External service adapters (shared across features)
│   ├── s3_service.py               # AWS S3 upload helpers
│   ├── canvas_service.py           # Canvas LMS integration (canvasapi library)
│   ├── nano_banana_client.py       # Gemini image generation for slides (NanoBananaClient)
│   ├── openai_vector_store.py      # OpenAI vector store CRUD helpers (create, upload, delete)
│   ├── perplexity_service.py       # Perplexity Agent API (deep-research preset) for curriculum research
│   ├── stripe_service.py           # Stripe customer/subscription helpers, webhook signature
│   └── email_service.py            # SES email sending
├── utils/
│   ├── token_utils.py              # extract_auth_token(), get_user_id_from_token(), set_auth_cookie()
│   ├── validation_utils.py         # get_client_ip(request), normalize_email(email)
│   ├── pdf_utils.py                # preprocess_pdf() — strips large PDFs to headings + first sentences before upload
│   ├── review_loop.py              # run_review_loop() — visual review retry logic (extracted for testability)
│   └── rendering/                  # pptx_renderer.py, html_renderer.py, chart_generator.py
├── exceptions/                     # Custom exception classes → global HTTP status mappings
│   ├── auth_error.py               # → 401
│   ├── not_found_error.py          # → 404
│   ├── permission_error.py         # → 403 (ownership checks in services)
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
- `/lessons` — `GET /{lesson_id}/pptx` and `GET /{lesson_id}/html` presigned URL endpoints
- `/parent` — parent invite and child lookup
- `/period` — period CRUD, homework agent; also the prefix for `ltg.py` (LTG conversation), which is a separate router file mounted under `/period`
- `/quest` — quest retrieval, submission
- `/slides` — `GET /{period_id}/pptx/status`, `POST /{period_id}/pptx/restart`
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

## Layer Rules

Rules below are the what; see [ARCH_DECISIONS.md](ARCH_DECISIONS.md) for the why.

- **Routers are HTTP-boundary-only.** Parse request, call service, return response. No business logic in `routers/`.
- **Service dependency injection.** Services declare DAOs, sub-services, integrations, and bot provider as constructor parameters with defaults (`def __init__(self, my_dao=None): self.my_dao = my_dao or MyDAO()`). Never instantiate inline.
- **`integrations/` vs `utils/` boundary.** `integrations/` = external service adapters (outbound calls, credentials). `utils/` = local computation only (no network, no credentials). Renderers (PPTX, HTML, charts) belong in `utils/rendering/`.
- **Auth enforcement split.** Role checks at router via `Depends(require_roles(...))`. Ownership checks raise `PermissionError` inside the service (because verification requires the same resource lookup). Enrollment checks at router top via `EnrollmentService().check_enrolled()` — service methods must not re-check enrollment.
- **All S3 access through `integrations/s3_service.py`.** Never instantiate `boto3.client` directly.

## Error Handling

Custom exceptions in `exceptions/` are caught by global handlers in `main.py`:

- `ValidationError` → 400
- `NotFoundError` → 404
- `AuthError` → 401
- `PermissionError` → 403
- bare `Exception` → 500 (catch-all; logs full traceback)

**Rule: route handlers must never catch bare `Exception` to convert it to a 500.** All unhandled exceptions bubble up to the global handler, which owns the 500 mapping. This keeps logging, error shape, and observability consistent across every route.

The only `except` clauses that belong in route handlers are intentional HTTP-branch mappings (e.g. `except MembershipRequiredError → 403`, `except ValueError → 400`) or intentional swallows where a sub-operation must not block the primary flow (e.g. billing trial-start during login — marked with a `# must not block <action>` comment).

Handlers that must perform cleanup before propagating (e.g. `shutil.rmtree` on a temp dir) should do so and then `raise` the original exception — never convert it to `HTTPException(500)`.

**Service guard methods must not use an `assert_` prefix.** Python's `unittest.mock` treats any attribute starting with `assert_` as a potential misspelled assertion helper and raises `AttributeError` at test time. Use `check_*` or `verify_*` instead (e.g. `check_enrolled`, `check_can_create_class`).

## Logging

Route handlers don't need explicit logging — FastAPI's access log covers them. Everything running **outside the request/response cycle** is invisible without it, so these must be logged:

- **BackgroundTasks and async pipelines**: log when the job starts (include relevant IDs and counts), when each significant step begins and completes, and when the job finishes.
- **Agent runs**: log before and after each `Runner.run()` call with enough context to identify which lesson/period/user triggered it.
- **External service calls** (S3, SES, Stripe, Perplexity): log failures with `exc_info=True`.
- **All `except` blocks that swallow exceptions**: always log with `exc_info=True` so the full traceback is captured, not just the exception type and message.

Use `logger = logging.getLogger(__name__)` at the top of every service and bot file that does any of the above.

## Auth Token Utilities

`utils/token_utils.py`:

- `extract_auth_token(request)` — reads Bearer header with cookie fallback
- `get_user_id_from_token(auth_token, session_dao)` — validates token, returns `user_id`, raises `AuthError` on failure
- `set_auth_cookie(response, token)` — sets `auth_token` cookie with environment-appropriate flags

## Constants

`constants/timeouts.py`:

- `JWT_EXPIRY_HOURS = 1` — JWT token lifetime
- `INVITE_EXPIRY_HOURS = 24` — parent invite expiry

See [bots/CLAUDE.md](bots/CLAUDE.md) for agent system and PPTX pipeline details.

## Development

**Setup** (always use venv):

```bash
cd eduquest-backend
make setup          # creates venv, installs all dependencies, installs pre-commit hook
source venv/bin/activate
```

**Environment** — `.env` file:

- `JWT_SECRET_KEY` — must match the frontend value exactly so cookies issued by either side verify on the other
- `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`
- `OPENAI_API_KEY`
- `PERPLEXITY_API_KEY` — required for `PerplexityService` (Perplexity Agent API)
- `GEMINI_API_KEY` (or `GOOGLE_API_KEY`) — required for `NanoBananaClient` (Gemini image generation for slides)
- `GEMINI_IMAGE_MODEL` (optional; defaults to `gemini-2.5-flash-image`)
- `AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `S3_BUCKET_NAME` — S3 uploads + SES email
- `SES_FROM_EMAIL`, `FRONTEND_BASE_URL` — password reset emails, Stripe redirect URLs
- `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` — Stripe API + webhook signature
- `STRIPE_PRICE_STARTER`, `STRIPE_PRICE_GROWTH`, `STRIPE_PRICE_PRO` — Stripe price IDs for each plan
- `PILOT_WAITLIST_ENABLED` (optional; default `true`)
- `MOCK_AI` (optional; set to `true` to use `MockBotProvider` in development — no OpenAI calls)

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
