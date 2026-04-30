# EduQuest Architecture Issues

Architectural issues and risks identified from the current codebase. Ordered roughly by impact.

---

## 1. `period.py` Router Is a God Object

**Problem:** `api/routers/period.py` is 388 lines and handles at least six unrelated concerns: LTG conversations, homework generation, file upload/management, period schedule CRUD, enrollment (verify, unenroll, accept parent invite), and period creation/listing. This is more than any other router and conflates boundaries that exist at the service layer.

**Why it's a problem:** Adding a feature to any one of these areas requires reasoning about the entire file. Bugs in the period schedule handler are buried next to enrollment logic. The router already has a private helper `_validate_pilot_access_p` (note the `_p` suffix suggesting it was distinguished from another `_validate_pilot_access` somewhere) — a sign the file is already working around its own naming collisions.

**Fix:** Split into at least three routers:
- `period.py` — period CRUD and file management
- `enrollment.py` (extend the existing one) — verify, unenroll, parent invite acceptance
- `schedule.py` — schedule generation and CRUD
- `ltg.py` — LTG conversation routes (could stay on period or move to conversation)

---

## 2. Two Parallel Auth Validation Patterns

**Problem:** The codebase has two ways to validate authentication:

1. `get_auth()` FastAPI dependency in `api/deps.py` — the idiomatic FastAPI approach, injected via `Depends(get_auth)` in router function signatures.
2. `require_auth(session_dao, auth_token, allowed_roles)` in `services/auth_utils.py` — an imperative helper that accepts a raw token and returns a `user_id`.

Both are used in router handlers. Some routes use `Depends(get_auth)`, others call `require_auth()` directly.

**Why it's a problem:** Two code paths means two places to update if auth logic changes (e.g. token format, expiry, role naming). It also means inconsistent error types — `get_auth()` raises `AuthError` (→ 401) but a caller of `require_auth()` might wrap or swallow the error differently.

**Fix:** Standardise on `Depends(get_auth)` for all route handlers. `require_auth()` in `auth_utils.py` is a service-layer concern that pre-dates FastAPI's DI system — remove it or restrict it to tests.

---

## 3. DynamoDB Dead Code Throughout Codebase

**Problem:** The app uses Supabase exclusively, but DynamoDB artifacts remain:

- `utils/conversion_utils.py::convert_decimals()` — docstring says "Recursively convert DynamoDB Decimal values to float". Still actively imported and called in `api/routers/conversation.py:108`.
- `services/waitlist/WaitlistService.py:53` — comment says "pass teacher_email for DynamoDB sort key".
- `data_access/password_reset_rate_limit_dao.py:31` — comment says "same signatures as DynamoDB version".
- `tests/conftest.py:62-63` — explicitly mocks `boto3.dynamodb` and `boto3.dynamodb.conditions` modules.
- `USE_SUPABASE` env flag — implies DynamoDB is a valid alternative when it isn't.

**Why it's a problem:** `convert_decimals()` in the grading path is dead transformation logic — Supabase returns Python floats, not `Decimal` objects. It passes silently but obscures intent. The DynamoDB comments mislead anyone trying to understand the DAO contracts.

**Fix:** Delete `convert_decimals()` and its call sites. Remove `USE_SUPABASE` flag (the app is always Supabase). Clean up DynamoDB comments and test mocks.

**Status: Fixed.**

---

## 4. `bots/ltg_conversation_service.py` Backward-Compat Shim

**Problem:** `bots/ltg_conversation_service.py` is a re-export shim — it exists only to preserve old import paths with no logic of its own (per `CLAUDE.md`). It lives inside `bots/` (the AI agents package) rather than `services/`, adding to the confusion about where LTG business logic lives.

**Why it's a problem:** Anyone importing from `bots/ltg_conversation_service.py` is importing AI agent code through a wrapper that only exists for historical reasons. The two layers (bots vs services) already have a defined relationship; a file that blurs that is noise.

**Fix:** Update all import sites to import directly from the canonical module, then delete the shim. This is a one-line search-and-replace.

---

## 5. `services/teacher/` Is an Empty Package

**Problem:** `services/teacher/` contains only `__init__.py`. There is no `teacher_service.py` inside it. `CLAUDE.md` lists `teacher/` as containing `teacher_service.py` and `period_schedule_service.py`, but only an empty `__init__.py` exists.

**Why it's a problem:** The package exists in the declared architecture but has no content, suggesting either: (a) `teacher_service.py` was moved elsewhere and the empty directory wasn't cleaned up, or (b) teacher-specific logic was never extracted from the router. The router `api/routers/teacher.py` may contain inline logic that should live in a service.

**Fix:** Either populate the package with the teacher service logic or delete the empty directory. Update `CLAUDE.md` to match whichever state is correct.

---

## 6. `bots/guardrails.py` Called Across Layer Boundary

**Problem:** `services/conversation/profile_service.py` imports and calls `bots/guardrails.py::check_student_output_safety()`. The services layer depends on the bots layer.

**Why it's a problem:** The five-layer architecture defines `bots/` and `services/` as separate concerns — services orchestrate bots, but a service importing directly from inside the bots package makes the dependency graph circular or at minimum unclear. If the guardrail is a pre/post-processing step for all student-facing AI responses, it belongs either in the bots themselves or in a shared `utils/` module, not as a cross-package import.

**Fix:** Move `guardrails.py` to `utils/` (or `services/`) if it's general infrastructure, or have the bots apply it internally before returning results.

---

## 7. Three Overlapping Frontend API Client Abstractions

**Problem:** The frontend has three files in `lib/` that handle backend communication:

- `agent-proxy.ts` — the actual HTTP client; exports `proxyToAgent(request, path)` which forwards Next.js route handler requests to the FastAPI backend with the auth cookie attached.
- `api-client.ts` — imports `proxyToAgent` and re-exports a named `api` object with typed method wrappers.
- `api.ts` — also imports `proxyToAgent` and exports its own `api` object.

Both `api-client.ts` and `api.ts` wrap the same proxy function with different method sets, creating ambiguity about which one to use from any given component or route handler.

**Why it's a problem:** New routes get added to whichever file the author opens first, causing coverage drift. There is no canonical answer to "how do I call the backend from a Next.js route handler?"

**Fix:** Keep `agent-proxy.ts` as the single low-level client. Consolidate `api-client.ts` and `api.ts` into one typed API facade (e.g. `lib/backend.ts`). Delete the duplicate.

---

## 8. Enrollment Ownership Split Across Two Services

**Problem:** Enrollment logic is split between two service files in different packages:

- `services/enrollment/enrollment_service.py` — handles enrollment CRUD (get, list by period).
- `services/period/period_enrollment_service.py` — handles verify_and_enroll, unenroll, accept parent invite.

The `enrollment/` router delegates to the first; the `period/` router delegates to the second. Both operate on the same underlying table.

**Why it's a problem:** Adding a new enrollment rule (e.g. max students per period, duplicate check) requires knowing which file to edit. The split is historical (enrollment was added to the period router first) rather than intentional.

**Fix:** Consolidate into `services/enrollment/enrollment_service.py`. The `period_enrollment_service.py` operations are enrollment operations, not period operations.

---

## 9. `aggregated_metrics` Table Read Directly by Frontend

**Problem:** The frontend reads the `aggregated_metrics` Supabase table directly via the Supabase JS client, bypassing the FastAPI backend entirely. There is no `/metrics` API endpoint. The table schema is exposed as an implicit API contract in `types/database.ts`.

**Why it's a problem:** If the `aggregated_metrics` table is renamed, restructured, or moved behind an endpoint for access-control reasons, the frontend will break silently — there is no route handler, type annotation, or service class to update. RLS policy on the table is the only access control, and it cannot enforce application-level logic (e.g. "a student may only see their own metrics").

**Fix:** Add a `GET /quest/metrics` or `GET /user/metrics` endpoint in FastAPI that reads from `AggregatedMetricsDAO`. This also makes it possible to add caching, filtering, or computed fields without a schema migration.

---

## 10. `WaitlistService.py` Breaks Naming Convention

**Problem:** The waitlist service file is `services/waitlist/WaitlistService.py` (PascalCase). Every other service file in the project uses `snake_case` (e.g. `auth_service.py`, `period_management_service.py`, `quest_retrieval_service.py`).

**Why it's a problem:** Minor but real friction — `from services.waitlist.WaitlistService import WaitlistService` looks anomalous. Autocomplete and `find` by convention (`*_service.py`) won't surface it.

**Fix:** Rename to `waitlist_service.py` and update the single import in `api/routers/waitlist.py`.

---

## 11. `bots/mocks.py` Lives in Production Code

**Problem:** `bots/mocks.py` is a file containing test mocks for the bots package. It sits in the main package directory alongside production agent code.

**Why it's a problem:** Test infrastructure in the source package is imported accidentally (or never, making it dead weight). It also signals that the bots package boundary was designed with testability as an afterthought.

**Fix:** Move to `tests/unit/bots/mocks.py` or a `tests/` conftest fixture.

---

## 12. Known Unresolved Bug in `grading_agent.py`

**Problem:** The most recent commit message reads: *"Error in grading found in bots, but I won't touch it yet to prevent merge conflicts"*. The bug is acknowledged but not fixed or tracked in code.

**Why it's a problem:** Grading is a core, user-visible feature. An unfixed, uncommitted bug in `bots/grading_agent.py` means grading results may be silently wrong. The deferral reason (merge conflicts) suggests the fix exists somewhere but hasn't landed.

**Fix:** Land the fix. If it's on a separate branch, rebase and merge. Add a test that covers the affected grading path so the regression is caught automatically.

---

## 13. `bots/provider.py` — Unknown Purpose

**Problem:** `bots/provider.py` exists but is not mentioned in `CLAUDE.md` or `ARCHITECTURE.md`. Its role in the agent system is unclear without reading it.

**Why it's a problem:** Undocumented files in a small codebase suggest either dead code or load-bearing infrastructure that nobody owns.

**Fix:** Read the file. If it's active infrastructure (e.g. a model provider abstraction), document it. If it's unused, delete it.
