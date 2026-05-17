# Test Coverage Gaps

This document tracks areas of the backend that are **intentionally deferred** from unit testing, along with the specific blocker for each. It is distinct from the arch-decision-based omissions listed at the bottom, which are permanent by design.

Update this file when a gap is resolved or a new one is identified.

---

## Deferred Gaps (need a code or infra change first)

### `services/conversation/conversation_service.py` — S3 upload in `start_update_assistant`

**Risk:** The `s3_service.upload_file()` call at the point where a student submits a file (line ~194) has no `try/except` wrapper. A boto3 error crashes the grading endpoint with an unhandled 500 rather than a clean error message.

**Blocker:** The S3 call must be wrapped in `try/except` before the error path can be unit-tested. Without the wrapper, the only way to exercise the failure is with a real (or mocked) boto3 client, which is an integration concern.

**Fix when ready:** Wrap the upload in `try/except`, re-raise as `ValidationError` or log-and-swallow depending on desired UX, then add a unit test that passes a mock `s3_service` that raises and asserts the correct outcome.

---

### `services/slides/pptx_generation_service.py` — S3 upload + agent timeout in `_generate_one`

**Risk:** Two failure modes are untested:
1. The S3 upload calls after agent success have no `try/except`. A failed upload leaves the lesson status permanently stuck at `"generating"`.
2. The `asyncio.wait_for(..., timeout=900)` timeout path (15-minute per-slide timeout) is never exercised, so a silently hung agent would not be caught in tests.

**Blocker:** Same S3 issue as above. The asyncio timeout test additionally requires either a real event loop (pytest-asyncio) or a structured mock of `asyncio.wait_for`.

**Fix when ready:** Add `try/except` around the S3 upload; set the status to `"failed"` on S3 error. For the timeout: add `pytest-asyncio` and write an async test that mocks `asyncio.wait_for` to raise `asyncio.TimeoutError`.

---

### `services/auth/auth_service.py` — `_check_werkzeug_pbkdf2` legacy hash migration

**Risk:** Accounts created before the bcrypt migration silently fail the password upgrade if this path is broken. The `except Exception: pass` swallows any error.

**Blocker:** Low urgency — only reachable during login by pre-bcrypt legacy accounts, which are a small and shrinking population. The current test suite covers the bcrypt path fully.

**Fix when ready:** Extract `_check_werkzeug_pbkdf2` to a public function in `utils/` (per the private-method testing rule in ARCH_DECISIONS.md), then add a parametrized test with a real werkzeug pbkdf2 hash.

---

### `routers/deps.py` — `require_student_viewer` cross-role access

**Risk:** The dependency allows a teacher or parent to pass a `user_id` query param to view a student's data. The "not authorized" branches (teacher not enrolled in any shared period, parent not linked to student) are never exercised.

**Blocker:** Requires FastAPI `TestClient` wiring. The existing `test_rbac_audit.py` enforces that every route declares an auth dependency but does not exercise cross-role authorization logic.

**Fix when ready:** Add a `tests/unit/routes/test_deps.py` file with a minimal FastAPI app that mounts a test route using `require_student_viewer`. Use `TestClient` + mocked `EnrollmentService`/`ParentService` to exercise all branches.

---

### `services/enrollment/enrollment_service.py` — `_cleanup_tutorial_periods`

**Risk:** When a student enrolls in a real class, the tutorial period should be removed from their enrollments. If this is broken, students accumulate a stale tutorial enrollment.

**Blocker:** The private-method rule in ARCH_DECISIONS.md prevents direct testing. The happy-path `verify_period_id` test added in this sprint exercises `_cleanup_tutorial_periods` indirectly but does not assert the tutorial deletion specifically.

**Fix when ready:** Extract `_cleanup_tutorial_periods` to a public method (or rename it without the underscore) and add a test that verifies `enrollment_dao.delete_enrollment` is called with `TUTORIAL_PERIOD_ID` when the student is enrolled in the tutorial.

---

### `utils/pdf_utils.py` — `preprocess_pdf`

**Risk:** The heading-extraction and first-sentence-stripping logic that reduces large PDFs before OpenAI upload is untested. A regression could silently upload truncated or malformed content.

**Blocker:** Requires real PDF fixture files. The logic depends on `pdfminer` parsing output, which is not meaningful to stub. Fits integration or file-based tests better.

**Fix when ready:** Add a `tests/integration/utils/test_pdf_utils.py` with small real PDF fixtures (a digital PDF and a scanned/image PDF) and assert on the preprocessed text structure.

---

### `services/billing/membership_service.py` — `mark_reminder_sent`, `attach_stripe_customer`, `mark_subscription_canceled`

**Risk:** Low — these are one-liner DAO delegations. A regression would be caught by the Stripe webhook integration tests.

**Blocker:** None technical. Deferred because the unit tests would only verify that Python method dispatch works (the criterion for "thin facade" tests in ARCH_DECISIONS.md).

**Fix when ready:** Not recommended unless these methods grow real logic.

---

## Permanent Omissions (arch decision — not gaps)

These are **not** missing tests. They are intentionally excluded per [ARCH_DECISIONS.md](../ARCH_DECISIONS.md):

| Area | Reason |
|------|--------|
| `services/tracking/` (PostHog) | Fire-and-forget; failures are swallowed by design. Schema verification belongs in the PostHog test environment. |
| `period_service.py`, `quest_service.py` (thin facades) | One-liner delegators with no logic. Tests belong at the sub-service level. |
| Bot implementation internals (`bots/`) | Tested via `MockBotProvider` constructor injection; individual bot classes are not imported outside `bots/provider.py`. |
