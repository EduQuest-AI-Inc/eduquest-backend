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

#### Role and enrollment enforcement

Role enforcement lives exclusively at the **router layer** via FastAPI `Depends()`. Service methods never raise errors for role checks — they assume the caller is already authorized. Service-layer `PermissionError` is reserved for **ownership checks** only (e.g. a teacher editing another teacher's period) — ownership stays in the service because verifying it requires fetching the same resource the service needs anyway; moving it to the router would mean two queries for the same row.

Enrollment checks — verifying a user is a member of a specific period — are also an authorization concern, not business logic. They belong at the router layer. Since `period_id` always arrives from the request body, call `EnrollmentService().check_enrolled(user_id, period_id)` at the top of the handler, before any service call. Service methods must not perform enrollment checks.

**Exception:** `PeriodQuestService._check_enrolled` in `services/period/period_quest_service.py`. The `period_id` here is resolved from quest data fetched *inside* `ConversationService` — it is not present in the request body at router time, so the router cannot perform the check up front. The method is marked `# arch-ok` at its call site.

#### Canonical auth dependencies

Three roles: `Role.STUDENT`, `Role.TEACHER`, `Role.PARENT` — defined as a `str, Enum` in `api/deps.py` alongside `AuthPayload` and `get_auth()`.

Canonical dependencies (all in `api/deps.py`):

- `get_auth()` — validates JWT, returns `AuthPayload`; use when any authenticated user is allowed.
- `require_roles(Role.X, ...)` — restricts to one or more roles; declare in the route's `Depends()`.
- `require_student_viewer("param_name")` — use when a parent or teacher may optionally pass a student `user_id` to view that student's data.

Supabase RLS is the secondary enforcement layer. Do not duplicate RLS logic in Python.

Audit: `pytest tests/unit/routes/test_rbac_audit.py` verifies every route either has an auth dependency or is listed in `EXPLICITLY_PUBLIC_ROUTES`.

### Admin vs user client in DAO construction

Pass `jwt=jwt` to a DAO only when the method reads **solely the calling user's own rows** and RLS should enforce that boundary. For any cross-user read (fetching another user's record by their ID), instantiate the DAO without a JWT so the admin client is used and RLS is bypassed server-side. Mixing both in a single service constructor is intentional and expected — document it with a comment. The default pattern (`self.my_dao = my_dao or MyDAO()`) uses the admin client.


### Services must raise typed exceptions — no bare ValueError

Services must raise typed exceptions from `exceptions/` to signal HTTP-meaningful outcomes. Never raise bare `ValueError`, `LookupError`, or `Exception` for conditions that have a defined HTTP mapping. Use: `NotFoundError` for missing resources (→ 404), `ValidationError` for invalid input or state (→ 400), `PermissionError` for ownership violations (→ 403). System integrity failures (corrupt data, missing required fields) should raise `RuntimeError` and bubble to 500. Routers must never catch bare exceptions to infer status codes via substring matching — typed exceptions carry explicit meaning and global handlers own the status mapping.

### Log before raising on cross-user fetches that can silently return empty

If a service method performs a cross-user lookup (fetching another user's row by ID) and that row is missing due to a data integrity issue rather than normal application flow, log at `logger.error` before raising. This makes failures visible in EC2 logs without Supabase API log archaeology. Silent empty returns (returning `None` or `[]` where a row is required) should be logged at `logger.warning`.

### Shared resource fetching — fetch once at the router, pass the object down

When multiple services in a single request need the same database row, fetch it once in a router-level `Depends()` and pass the object as a parameter to every service that needs it. Services must not re-query a resource they have already been given.

The canonical example is `period`: routes that call several sub-services all operating on the same period should declare a `get_period(period_id, auth)` dependency in `deps.py` that fetches the row once and raises `NotFoundError` if missing. Each service method then accepts a `Period` parameter instead of a `period_id` and never calls the DAO itself.

This is the inverse of the ownership-check rule above: ownership checks stay in the service because the service is the first to fetch the resource; shared-resource fetching moves to the router because the resource is needed before any service is called and would otherwise be fetched redundantly by each one.

### The bot provider is selected once at startup — services depend on the protocol, never the implementation

`os.getenv("MOCK_AI")` is read exactly once, in `main.py` lifespan, and the result is stored in `app.state.bot_provider`. After startup, no code reads `MOCK_AI` again. `get_bot_provider()` in `api/deps.py` is a thin FastAPI dependency that reads `request.app.state.bot_provider` — it contains no selection logic.

All type annotations for the bot provider use `BotProviderProtocol` from `bots/protocol.py`, never the concrete `BotProvider` or `MockBotProvider` class. `BotProviderProtocol` is a `@runtime_checkable Protocol`: any object that implements all factory methods satisfies it without inheritance. Depending on a concrete class defeats the abstraction and prevents swapping implementations.

Individual bot classes (`HWAgent`, `GradingOrchestrator`, `CurriculumAgent`, etc.) are never imported or instantiated outside `bots/provider.py`. All bot creation goes through the provider factory methods. A direct import bypasses the abstraction boundary — if the provider is swapped, a directly-instantiated bot silently runs against the wrong configuration.

### `@function_tool` wrappers are agent-boundary-only — same rule as routers

A `@function_tool` body must do nothing except call a named public function and return its result. All business logic belongs in that extracted function, which accepts its dependencies as parameters. No module-level instantiation in `bots/tools/` files; use lazy initialisation (`_x: T | None = None`, set on first call) for any singleton that the thin wrapper needs to supply as a default.

This is the agent-layer equivalent of "Routers are HTTP-boundary-only." The extracted function lives in `utils/` if it is pure control flow with injected dependencies, or in a dedicated service if it needs its own DAO/provider wiring.

`SLIDE_TOOLS` calling `ContentWriterAgent` and `VisualReviewAgent` as sub-agents is the intended multi-agent design and is **not** a violation of the "individual bot classes never imported outside `bots/provider.py`" rule. See [bots/CLAUDE.md](bots/CLAUDE.md) for the full call chain and mock boundary details.

### Services receive their dependencies — they never instantiate DAOs, services, integration modules, or the bot provider inline

Service classes must declare their DAOs, sub-services, integration modules, and bot provider as constructor parameters with defaults, not create them inside methods. This is what makes unit tests possible without `@patch` — tests pass mock objects directly to the constructor.

**Every dependency must use the `or` injectable pattern** — no exceptions for DAOs that "always need the admin client" or integration factories like `get_email_service()`. If a dependency has no sensible default-inject path, make it keyword-only with a default of `None` and build the real instance in the `or` branch.

```python
# Correct — every dependency is injectable
class MyService:
    def __init__(self, my_dao=None, email_service=None):
        self.my_dao = my_dao or MyDAO()
        self.email_service = email_service or get_email_service()

# Wrong — some deps injectable, others hardwired. Hides Supabase/SES calls in tests.
class MyService:
    def __init__(self, my_dao=None):
        self.my_dao = my_dao or MyDAO()
        self.email_service = get_email_service()   # untestable without @patch

# Wrong — DAO created inside a method body, invisible to the constructor
def run_something(user_id):
    dao = MyDAO()   # forces @patch, breaks when file is renamed
```

**Detection:** `grep -rn "DAO()\|Service()\|get_email_service()\|get_.*_service()" services/` — any hit that is not in an `or`-branch (`x or MyDAO()`) or a `_lazy_getter` is a violation.

**Lazy getter exception:** A service may use private `_get_X()` methods that instantiate dependencies on first call if (a) the service's `__init__` still accepts the dependency as an optional parameter with default `None`, and (b) the getter checks `if self._x is None` before instantiating. This pattern (`services/auth/account_deletion_service.py`) is acceptable when the service has many optional role-specific dependencies that are expensive to construct up front and only one code path ever needs them. Tests still pass mock objects directly to the constructor. Dynamic imports inside the getter body are allowed because the import is co-located with the instantiation — but do not use this as a reason to skip adding the parameter to `__init__`.

```python
# Correct lazy getter — constructor accepts the parameter; getter is just deferred construction
class MyService:
    def __init__(self, heavy_dao=None):
        self._heavy_dao = heavy_dao

    def _get_heavy_dao(self):
        if self._heavy_dao is None:
            from data_access.heavy_dao import HeavyDAO
            self._heavy_dao = HeavyDAO()
        return self._heavy_dao
```

**Dynamic import variant:** A `from data_access.X import Y` or `from services.X import Y` statement indented inside a method body that is NOT part of a lazy getter is a red flag — it usually means the dependency was never added to the constructor. Move the import to module level and the instantiation to `__init__`.

**JWT-parameterized DAOs still need injectable defaults.** `self.student_dao = StudentDAO(jwt=jwt)` is not injectable — a test cannot swap in a mock DAO without `@patch`. The fix is `self.student_dao = student_dao or StudentDAO(jwt=jwt)` with `student_dao=None` added to the `__init__` signature. Tests pass mock objects; production passes nothing and gets the JWT-scoped real DAO.

**Test signal:** If a test calls `MyService.__new__(MyService)` to bypass `__init__`, that is a sign that the service has hardwired dependencies. Fix the service constructor instead of working around it with `__new__`.

The bot provider follows the same rule. Services declare `bot_provider: BotProviderProtocol` as a constructor parameter and store it as `self._bot_provider`. No service imports or calls `get_bot_provider()` directly — that is the router's job via `Depends()`.

Module-level orchestration functions (`run_*`) are also banned for the same reason. If logic needs its own DAOs, it belongs in a service class, not a free function.

### Cross-domain service dependencies — allowed flow and forbidden patterns

Services in different feature domains may depend on each other, but only in one direction and only via constructor injection. The allowed dependency flow is:

```
conversation ──→ period / quest   (one-way; injected at constructor)
period       ──→ enrollment / curriculum / quest   (one-way; injected at constructor)
quest        ──→ curriculum   (one-way; injected at constructor)
```

**Forbidden patterns:**

- **Dynamic imports inside method bodies** — `from services.X import Y` inside a function hides the dependency from the constructor, making it invisible to callers and impossible to inject in tests. All cross-domain service dependencies must be declared as constructor parameters with defaults (same rule as DAOs).
- **Reverse-direction imports** — `period` and `quest` domains must not import from the `conversation` domain. (`period_service.py` currently imports `LTGOrchestrationService` from `services/conversation/ltg_service.py` — this is a tracked violation to address when `PeriodService` is refactored, not a precedent to copy.)
- **Router-level service construction of another domain's private API** — a router handler must not call a private method (underscore-prefixed) on a service from a different domain. Use a public method or add one.

**Rationale:** Hidden cross-domain calls break the "refactor one domain, break the other at runtime not compile time" guarantee. Constructor injection makes the dependency explicit, testable with mocks, and visible in `__init__` signatures.

### `integrations/` vs `utils/` — network boundary rule

The distinction between these two directories is whether the code needs a network call or a credential to function:

- `integrations/` — external service adapters that make outbound network calls or require API credentials at runtime (S3, Canvas, Stripe, SES, Perplexity). These cannot run offline.
- `utils/` — local library computation that runs offline: string manipulation, token handling, pure-Python rendering (matplotlib charts, python-pptx layout, Jinja2 HTML). No credentials, no network.

Renderers (PPTX, HTML, chart generation) belong in `utils/rendering/` because they are local library calls using matplotlib, python-pptx, and Jinja2 — no API keys, no network. They must not live under `services/` or `integrations/`.

### Every route handler must declare `response_model=` pointing to a DTO in `responses/`

All route handlers must declare `response_model=` pointing to a Pydantic DTO in `eduquest-backend/responses/`. No handler may return an untyped dict without a corresponding response model. DTOs live in `responses/[router_name].py` and use `model_config = ConfigDict(extra="ignore")` so extra fields from Supabase dicts are stripped rather than causing validation errors.

When a router or response file changes, `openapi.json` must be regenerated (via the `export-openapi` pre-commit hook or manually) and committed alongside the change. This keeps FastAPI's OpenAPI schema accurate and allows `openapi-typescript` to generate correct frontend types automatically. Bypassing this with `--no-verify` is a policy violation, not just a hook skip.

Agent and conversation endpoints where output structure is not yet stable may use `response_model=dict[str, Any]` as a placeholder so they appear in the schema.

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

### Response model field types must match the database column types

`responses/` Pydantic fields must use the Python type the database actually returns — pay particular attention to `integer → int`, `boolean → bool`, and `text[] → list[str]`. A mismatch raises a `ResponseValidationError` (500) the first time that endpoint is hit with real data, not at startup. Mock data in route tests must use the same types, or the test will pass against the wrong declaration and hide the bug. `tests/unit/routes/test_response_model_types.py` enforces compatibility between domain models and response models automatically.

### No `PYTEST_CURRENT_TEST` guards in production code

Production code must never contain `if os.getenv("PYTEST_CURRENT_TEST"): raise`. This pattern hides failure paths from tests rather than fixing them — it makes a broad `except` behave differently in tests and in production, which defeats the purpose of testing. If a broad `except` makes a failure mode untestable, split the `try` block into narrower scopes instead (one for the agent/external-call result, one for the S3 upload, etc.) so each can be exercised independently by injecting a mock that raises.

### External service calls in services must be wrapped in `try/except`

Every call to S3, Stripe, SES, Canvas, Perplexity, or any other external service inside a service method must be wrapped in `try/except`. For non-critical side-effects (audit uploads, analytics, fire-and-forget notifications) log-and-swallow with `exc_info=True` and continue. For operations that are critical to the caller's primary flow, re-raise as `ValidationError` (400) with a user-facing message. Bare unhandled exceptions from external clients produce opaque 500s that are invisible in monitoring until a user reports them and block all preceding work (e.g. a grading result already computed) from reaching the user.
