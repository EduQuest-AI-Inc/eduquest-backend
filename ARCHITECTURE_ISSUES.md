# EduQuest Architecture Issues

Architectural issues and risks identified from the current codebase. Ordered roughly by impact.

---

## 1. Router Error Handling Leaks Internal Messages

**Problem:** Several routers (e.g. `api/routers/ltg.py`) catch `ValueError`, `LookupError`, and bare `Exception` and re-raise them as `HTTPException` with `detail=str(e)`. This pattern appears in at least the three routes in `ltg.py`.

**Why it's a problem:** `str(e)` on an unexpected exception exposes internal stack details, module paths, or data values to the client. It also duplicates error-mapping logic that already exists — `main.py` registers global handlers for `ValidationError` → 400, `NotFoundError` → 404, and `AuthError` → 401. Routes that re-implement this mapping by hand will drift from the global policy and produce inconsistent status codes.

**Fix:** Remove the `try/except` blocks from router handlers. Raise `ValidationError`, `NotFoundError`, or `AuthError` (from `exceptions/`) in the service layer and let the global handlers in `main.py` catch them. Reserve inline `try/except` only for truly route-specific logic that cannot be expressed as a typed exception.
