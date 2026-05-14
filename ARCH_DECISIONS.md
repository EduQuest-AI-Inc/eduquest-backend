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

Role enforcement lives exclusively at the **router layer** via FastAPI `Depends()`. Service methods never raise errors for role checks — they assume the caller is already authorized. Service-layer `PermissionError` is reserved for **ownership checks** only (e.g. a teacher editing another teacher's period) — ownership stays in the service because verifying it requires fetching the same resource the service needs anyway; moving it to the router would mean two queries for the same row.

Enrollment checks — verifying a user is a member of a specific period — are also an authorization concern, not business logic. They belong at the router layer. Since `period_id` always arrives from the request body, call `EnrollmentService().check_enrolled(user_id, period_id)` at the top of the handler, before any service call. Service methods must not perform enrollment checks.

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

### The bot provider is selected once at startup — services depend on the protocol, never the implementation

`os.getenv("MOCK_AI")` is read exactly once, in `main.py` lifespan, and the result is stored in `app.state.bot_provider`. After startup, no code reads `MOCK_AI` again. `get_bot_provider()` in `api/deps.py` is a thin FastAPI dependency that reads `request.app.state.bot_provider` — it contains no selection logic.

All type annotations for the bot provider use `BotProviderProtocol` from `bots/protocol.py`, never the concrete `BotProvider` or `MockBotProvider` class. `BotProviderProtocol` is a `@runtime_checkable Protocol`: any object that implements all factory methods satisfies it without inheritance. Depending on a concrete class defeats the abstraction and prevents swapping implementations.

Individual bot classes (`HWAgent`, `GradingOrchestrator`, `CurriculumAgent`, etc.) are never imported or instantiated outside `bots/provider.py`. All bot creation goes through the provider factory methods. A direct import bypasses the abstraction boundary — if the provider is swapped, a directly-instantiated bot silently runs against the wrong configuration.

### `@function_tool` wrappers are agent-boundary-only — same rule as routers

A `@function_tool` body must do nothing except call a named public function and return its result. All business logic belongs in that extracted function, which accepts its dependencies as parameters. No module-level instantiation in `bots/tools/` files; use lazy initialisation (`_x: T | None = None`, set on first call) for any singleton that the thin wrapper needs to supply as a default.

This is the agent-layer equivalent of "Routers are HTTP-boundary-only." The extracted function lives in `utils/` if it is pure control flow with injected dependencies, or in a dedicated service if it needs its own DAO/provider wiring.

### Services receive their dependencies — they never instantiate DAOs, services, integration modules, or the bot provider inline

Service classes must declare their DAOs, sub-services, integration modules, and bot provider as constructor parameters with defaults, not create them inside methods. This is what makes unit tests possible without `@patch` — tests pass mock objects directly to the constructor.

```python
# Correct
class MyService:
    def __init__(self, my_dao=None):
        self.my_dao = my_dao or MyDAO()

# Wrong — hides a Supabase dependency, forces class-level patching in tests
def run_something(user_id):
    dao = MyDAO()   # untestable without @patch
```

The bot provider follows the same rule. Services declare `bot_provider: BotProviderProtocol` as a constructor parameter and store it as `self._bot_provider`. No service imports or calls `get_bot_provider()` directly — that is the router's job via `Depends()`.

Module-level orchestration functions (`run_*`) are also banned for the same reason. If logic needs its own DAOs, it belongs in a service class, not a free function.

### `integrations/` vs `utils/` — network boundary rule

The distinction between these two directories is whether the code needs a network call or a credential to function:

- `integrations/` — external service adapters that make outbound network calls or require API credentials at runtime (S3, Canvas, Stripe, SES, Perplexity). These cannot run offline.
- `utils/` — local library computation that runs offline: string manipulation, token handling, pure-Python rendering (matplotlib charts, python-pptx layout, Jinja2 HTML). No credentials, no network.

Renderers (PPTX, HTML, chart generation) belong in `utils/rendering/` because they are local library calls using matplotlib, python-pptx, and Jinja2 — no API keys, no network. They must not live under `services/` or `integrations/`.

---

## Testing Decisions

### Thin facade services do not get their own unit test files

`period_service.py` and `quest_service.py` are self-described thin orchestrators — every method is a one-liner delegation to a sub-service. Testing them would only verify that Python method dispatch works. Tests belong at the sub-service level where logic actually lives (`period_quest_service.py`, `quest_creation_service.py`, etc.). If a facade grows real logic it stops being a facade — move that logic to a sub-service instead.

### `services/tracking/` is intentionally untested

PostHog analytics calls are fire-and-forget by design — failures are swallowed so tracking never breaks product flows. Writing unit tests for these wrappers would only verify that the PostHog SDK was called correctly, which is testing the vendor. If the event schema needs to be verified, do it via a PostHog test environment, not a unit test.

### Bot mocking uses `MockBotProvider()` constructor injection — no `sys.modules` stubbing or `patch()` calls

Tests that need a mock bot provider pass `MockBotProvider()` directly to the service constructor — the same way the router wires it in production via `Depends()`. `conftest.py` must not replace any module under `bots/` with `MagicMock()`, and `patch("services.X.get_bot_provider")` is banned. Module replacement creates invisible fakes: new bot modules added after the stub are silently mocked with no warning, and test failures are indistinguishable from real runtime errors. Patching import paths breaks on file renames and never exercises the real `Depends()` wiring.

`MockBotProvider` must satisfy `BotProviderProtocol` — verified by `tests/unit/bots/test_provider_compliance.py` which asserts `isinstance(MockBotProvider(), BotProviderProtocol)`. Any PR that adds a factory method to `BotProvider` must add the same method to both `BotProviderProtocol` and `MockBotProvider` before it merges. The motivating incident: `MockBotProvider` was missing `create_pptx_agent()` after the method was added to the real provider. The resulting `TypeError` was swallowed by a bare `except Exception`, recorded as `status='failed'`, and looked identical to a real agent crash.

### Private methods are tested through the public API, not directly

Test files must not call underscore-prefixed methods (`_check_profile`, `_extract_conversation_id`, etc.) directly. If the public-facing method covers all branches of a private method, the private tests are redundant and create rename-friction. If a private method is complex enough that the public path cannot reach all its branches in isolation, the right fix is to make it a standalone public function in a utility module — not to test it directly while leaving it private.
