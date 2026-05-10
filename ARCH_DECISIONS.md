# EduQuest Backend — Decisions

## Architecture Decisions

### Routers are HTTP-boundary-only — no business logic lives there

Route handlers in `routers/` are responsible for parsing requests, enforcing auth via `Depends()`, and returning responses. All business logic belongs in the service layer. A router handler should do nothing more than call a service method and return its result (plus any private `_helper()` functions scoped to that file for multi-step request wiring, capped at 20 lines each).

### All S3 access goes through `integrations/s3_service.py`

AWS credentials, bucket config, and error handling live in one place. Services must never
instantiate `boto3.client` directly — import helpers from `integrations/s3_service.py` instead.

### Frontend role and ownership checks are UX only — the backend is the enforcement boundary

The frontend may hide buttons, redirect routes, or skip rendering components based on role or ownership. These checks exist to avoid confusing users with options that would fail, not to enforce access control. Every protected action must be independently enforced at the API layer via `require_roles` or an explicit ownership check. Removing a frontend gate should never expose a security gap.

### Auth & Role-Based Access Control

Role enforcement lives exclusively at the **router layer** via FastAPI `Depends()`. Service methods never raise errors for role checks — they assume the caller is already authorized. Service-layer `PermissionError` is reserved for **ownership checks** only (e.g. a teacher editing another teacher's period).

Three roles: `Role.STUDENT`, `Role.TEACHER`, `Role.PARENT` — defined as a `str, Enum` in `api/deps.py` alongside `AuthPayload` and `get_auth()`.

Canonical dependencies (all in `api/deps.py`):

- `get_auth()` — validates JWT, returns `AuthPayload`; use when any authenticated user is allowed.
- `require_roles(Role.X, ...)` — restricts to one or more roles; declare in the route's `Depends()`.
- `require_student_viewer("param_name")` — use when a parent or teacher may optionally pass a student `user_id` to view that student's data.

Supabase RLS is the secondary enforcement layer. Do not duplicate RLS logic in Python.

Audit: `pytest tests/unit/routes/test_rbac_audit.py` verifies every route either has an auth dependency or is listed in `EXPLICITLY_PUBLIC_ROUTES`.

### The frontend never calls Supabase for data reads or writes — all domain data goes through FastAPI

The frontend uses the Supabase client SDK for auth only (sign-up, sign-in, session management).
All domain data reads and writes must go through the FastAPI backend. This keeps business logic
and RLS policy in one place and prevents clients from bypassing server-side validation.

### All agent instantiation goes through `bots/provider.py::get_bot_provider()`

Services must never import agent classes directly. All bot creation must go through `get_bot_provider()`. This is what makes `MOCK_AI=true` (env flag) and `set_bot_provider(MockBotProvider())` (test setup) work — swapping the provider swaps every agent at once without touching service code. A direct import bypasses the provider and silently breaks the mock system, causing tests to make real OpenAI calls or fail without a clear cause.

---

## Testing Decisions

### Thin facade services do not get their own unit test files

`period_service.py` and `quest_service.py` are self-described thin orchestrators — every method is a one-liner delegation to a sub-service. Testing them would only verify that Python method dispatch works. Tests belong at the sub-service level where logic actually lives (`period_quest_service.py`, `quest_creation_service.py`, etc.). If a facade grows real logic it stops being a facade — move that logic to a sub-service instead.

### `services/tracking/` is intentionally untested

PostHog analytics calls are fire-and-forget by design — failures are swallowed so tracking never breaks product flows. Writing unit tests for these wrappers would only verify that the PostHog SDK was called correctly, which is testing the vendor. If the event schema needs to be verified, do it via a PostHog test environment, not a unit test.

### Private methods are tested through the public API, not directly

Test files must not call underscore-prefixed methods (`_check_profile`, `_extract_conversation_id`, etc.) directly. If the public-facing method covers all branches of a private method, the private tests are redundant and create rename-friction. If a private method is complex enough that the public path cannot reach all its branches in isolation, the right fix is to make it a standalone public function in a utility module — not to test it directly while leaving it private.
