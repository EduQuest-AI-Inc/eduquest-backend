# CLAUDE.md — Backend

See also: [data_access/CLAUDE.md](data_access/CLAUDE.md) for DAO and database patterns.
See also: [ARCH_DECISIONS.md](ARCH_DECISIONS.md) for authoritative decisions on router boundaries, auth enforcement, enrollment checks, agent instantiation, service dependencies, and testing conventions.
See also: [ARCHITECTURE.md](ARCHITECTURE.md) for a full narrative walkthrough of every layer and pipeline.

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
│   ├── demo_quest.py               # /demo — POST /quest (no auth, landing page)
│   ├── enrollment.py               # /enrollment — enroll/unenroll students
│   ├── feedback.py                 # /feedback — student/teacher feedback submission and retrieval
│   ├── lessons.py                  # /lessons — presigned URLs for lesson PPTX and HTML
│   ├── ltg.py                      # /period — LTG conversation routes (mounted under /period)
│   ├── marketplace.py              # /marketplace — resource marketplace operations
│   ├── parent.py                   # /parent — parent invite, child lookup
│   ├── period.py                   # /period — period CRUD, homework agent, file uploads
│   ├── quest.py                    # /quest — quest retrieval, submission
│   ├── slides.py                   # /slides — PPTX status by period, restart generation
│   ├── teacher.py                  # /teacher — Canvas courses, skill-mastery analytics
│   ├── user.py                     # /user — user profile, tutorial state
│   ├── waitlist.py                 # /pilot-waitlist — status, join
│   └── demo_quest.py               # /demo-quest — demo quest routes
├── services/                         # Service/business logic layer (imported by routers/)
│   ├── auth/                       # auth_service.py, oauth_service.py,
│   │                               #   password_reset_service.py, password_policy.py
│   ├── auth/                       # auth_service.py, supabase_auth_service.py, oauth_service.py,
│   │                               #   password_reset_service.py, password_policy.py, account_deletion_service.py
│   ├── billing/                    # membership_service.py (trial lifecycle, plan limits,
│   │                               #   Stripe sync), trial_reminder_service.py
│   ├── conversation/               # conversation_service.py, grading_service.py,
│   │                               #   ltg_service.py, profile_service.py, teacher_feedback_service.py
│   ├── curriculum/                 # curriculum_service.py
│   ├── demo/                       # demo_ltg_service.py (public landing-page quest demo)
│   ├── enrollment/                 # enrollment_service.py (CRUD, verify_and_enroll, unenroll,
│   │                               #   get_my_periods, assert_enrolled)
│   ├── feedback/                   # feedback_service.py
│   ├── knowledge_graph/            # knowledge_graph_service.py
│   ├── lessons/                    # lessons_service.py
│   ├── marketplace/                # marketplace_service.py
│   ├── period/                     # period_service.py, period_quest_service.py,
│   │                               #   period_management_service.py, period_file_service.py,
│   │                               #   period_summer_quest_service.py
│   ├── quest/                      # quest_service.py, quest_creation_service.py,
│   │                               #   quest_retrieval_service.py, quest_grading_service.py
│   ├── tracking/                   # PostHog server-side analytics (posthog_client.py,
│   │                               #   events.py, track.py)
│   ├── user/                       # user_service.py, teacher_service.py
│   │                               #   events.py, track.py) — see [services/tracking/README.md](services/tracking/README.md)
│   ├── user/                       # user_service.py, teacher_service.py
│   ├── demo/                       # demo_ltg_service.py
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
│   ├── password_reset_token.py     # PasswordResetToken — reset link token
│   ├── week.py                     # Week — weekly division within a period
│   ├── lesson.py                   # Lesson — lesson unit within a week
│   ├── lesson_pptx.py              # LessonPptx — per-lesson PPTX generation state & S3 reference
│   ├── slide_plan.py               # SlidePlan — PPTX generation plan
│   ├── concept.py                  # Concept — concept taught in a lesson
│   ├── skill.py                    # Skill — measurable skill with mastery config
│   ├── concept_skill.py            # ConceptSkill — concept ↔ skill junction
│   └── marketplace_listing.py      # MarketplaceListing — resource marketplace entry
├── bots/                           # All AI agent code (subdirectory-organized)
│   ├── grading_agent.py            # Multi-agent grading orchestrator
│   ├── ltg_agent.py                # Long-term goal agent
│   ├── guardrails.py               # Content safety guardrails
│   ├── model_config.py             # Central model-name and reasoning policy
│   ├── profile_agent.py            # Student profile agent
│   ├── protocol.py                 # BotProviderProtocol, PptxAgentProtocol
│   ├── provider.py                 # BotProvider factory for real and mock instances
│   ├── teacher_feedback_agent.py   # Teacher feedback agent
│   ├── tracing.py                  # Agents SDK trace helpers (hashed group IDs, sanitized metadata)
│   ├── _mocks.py                   # MockBotProvider and mock agents for testing
│   ├── curriculum/                 # curriculum_agent.py (Week→Lesson→Concept→Skill),
│   │                               #   coverage_evaluator.py (decides Perplexity research)
│   ├── quests/                     # quest_agent.py (HWAgent — instructions/rubric),
│   │                               #   ltg_schedule_agent.py (LTG → per-week quest names),
│   │                               #   curriculum_only_quest_agent.py (Summer Side Quests),
│   │                               #   demo_ltg_agent.py (public landing-page demo)
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

- `/auth` — login, signup (`trial_confirmed: true` is required for parent/teacher), OAuth complete, password reset
- `/billing` — `GET /membership`, `POST /checkout-session`, `POST /portal-session`, `POST /webhook`
- `/conversation` — profile assistant, update assistant
- `/curriculum` — curriculum generation/approval per period
- `/demo` — public `POST /quest` landing-page quest demo, no auth required
- `/enrollment` — student enrollment
- `/lessons` — `GET /{lesson_id}/pptx` and `GET /{lesson_id}/html` presigned URL endpoints
- `/parent` — parent invite and child lookup
- `/period` — period CRUD, homework agent; also the prefix for `ltg.py` (LTG conversation), which is a separate router file mounted under `/period`
- `/quest` — quest retrieval, submission
- `/slides` — `GET /{period_id}/pptx/status`, `POST /{period_id}/pptx/restart`
- `/teacher` — Canvas courses, skill-mastery analytics
- `/user` — user profile, tutorial state
- `/pilot-waitlist` — status, join
- `/feedback` — student/teacher feedback submission and retrieval
- `/marketplace` — resource marketplace: browse, fork, publish

## Membership / Trial Lifecycle

`MembershipService` (`services/billing/membership_service.py`) is the only seam that creates and reads memberships:

- `start_trial_if_eligible(user_id, role)` — idempotent; creates a `trialing` row valid for `TRIAL_DAYS = 14` (no card collected). Called from `routers/auth.py:signup`, `routers/auth.py:login`, and OAuth completion (the login/OAuth calls are backfills for legacy accounts).
- `evaluate_access(user_id, role) → MembershipAccess` — used by `assert_can_create_class` / `assert_can_add_student_to_period`. Self-heals expired trials (status flips to `expired`).
- `apply_stripe_subscription(subscription)` — invoked from the `/billing/webhook` handler on `customer.subscription.*` and `checkout.session.completed`.

Both auth handlers wrap the trial call in `try/except` so signup/login never fail because of billing. Because of that, **bugs in `start_trial_if_eligible` are silent** — instrument inside the service and inspect the swallowed exception when debugging missing-trial reports. Watch out: any `Optional[str] = None` Pydantic field on a `NOT NULL` column will fail with PostgREST `23502` — use `default_factory` instead (see `Membership.updated_at`).

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
- **`response_model=` required on every route handler.** Must point to a DTO in `responses/`.
- **Fetch shared resources once at the router.** Pass the fetched object down to services — never re-fetch inside a service method.
- **Admin vs user Supabase client.** DAOs operating in user context pass the user JWT (RLS enforced). DAOs needing elevated access use the service-role client. Set in the DAO constructor.
- **Services raise typed exceptions only.** No bare `ValueError` or `Exception` — use types from `exceptions/`.
- **Cross-domain service dependencies.** A service may import DAOs and sub-services within its own domain. Cross-domain imports are allowed only downward. See ARCH_DECISIONS.md for the allowed/forbidden matrix.
- **Log before raising on cross-user fetches.** If a fetch can silently return empty due to RLS, log the relevant IDs before raising so failures are diagnosable.
- **External service calls in services must be wrapped in `try/except`.** Failures in S3, SES, Stripe, and Perplexity must not propagate as untyped exceptions.

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

OAuth uses Supabase Auth only as an external identity-provider bridge. `routers/auth.py:/oauth/complete` accepts the Supabase access token, `services/auth/oauth_service.py` verifies it with `GET /auth/v1/user`, creates or finds the EduQuest account in the normalized user tables, then mints the normal EduQuest custom JWT. Do not store Supabase sessions as app sessions.

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

Developer scripts: [scripts/README.md](scripts/README.md). AWS infrastructure: [cloudformation/README.md](cloudformation/README.md).

**Setup** (always use venv):

```bash
cd eduquest-backend
make setup          # creates venv, installs all dependencies, installs pre-commit hook
source venv/bin/activate
```

**Environment** — `.env` file:

- `JWT_SECRET_KEY` — backend JWT signing key; frontend uses Supabase Auth directly (no longer shared)
- `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_ANON_KEY` (from Supabase Dashboard → Settings → API → anon public)
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

# Unit tests run fully offline — all external services (OpenAI, boto3, Supabase) are mocked.
# Integration tests require a live Supabase connection (.env with real credentials).

eduquest-backend/venv/bin/pytest eduquest-backend/tests/unit/   # offline, no .env needed
pytest -m unit
pytest -m integration
pytest -m auth
pytest tests/test_teacher_dao.py
pytest --cov=. --cov-report=html
```

Configuration in [pytest.ini](pytest.ini). Markers: unit, integration, auth, api, smoke, slow.
