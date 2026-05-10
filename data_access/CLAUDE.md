# CLAUDE.md — Data Access

All DAOs live in `data_access/` and extend `SupabaseBaseDAO` from [base_dao.py](base_dao.py).

## DAO Pattern

```python
from data_access.base_dao import SupabaseBaseDAO

class ExampleDAO(SupabaseBaseDAO):
    def __init__(self):
        super().__init__('table_name')
```

One file per Supabase table.

## Base helpers (read these before adding methods)

`SupabaseBaseDAO` exposes thin wrappers around the PostgREST query builder:

- `_select_by_id(id_column, id_value)` — single-row lookup via `.maybe_single()`; only use on true primary key columns
- `_select_eq(column, value)` — multi-row lookup as a list; use this for any UNIQUE non-PK column (email, code, hash, etc.) — `maybe_single()` returns `None` for both "0 rows" and silent PostgREST failures, making bugs invisible
- `_insert(data)` — strict insert; raises on conflict
- `_upsert(data)` — insert-or-update on primary key
- `_update(filters, updates)` — partial update; returns the updated rows
- `_delete(filters)` — returns the deleted rows
- `_rpc(function_name, params)` — call a Postgres function

> **Watch out:** `_upsert` and `_insert` pass the dict straight to PostgREST including `null` values. Any Pydantic field declared `Optional[str] = None` that maps to a `NOT NULL` Supabase column will fail with Postgres error code `23502`. Either give the field a `default_factory` (mirroring `Membership.created_at` / `Membership.updated_at`), or relax the column to nullable in the schema. **Do not** silently swallow these errors — wrap calls in `try/except` only at clear safety boundaries (e.g. signup), and surface the failure when debugging.

## Normalized User Tables

Shared identity fields live in the `user` table:

- `first_name`, `last_name`, `email` (UNIQUE constraint), `password`, `last_login`

Role tables (`student`, `teacher`, `parent`) hold only role-specific fields and a FK to `user.user_id` with `ON DELETE CASCADE`.

## Identity DAOs

**UserDAO** ([user_dao.py](user_dao.py)):

- `get_by_id`, `get_by_email`, `update`, `delete`
- All email uniqueness checks and password resets go through `UserDAO` directly — no need to query all three role tables

**Role DAOs** ([student_dao.py](student_dao.py), [teacher_dao.py](teacher_dao.py), [parent_dao.py](parent_dao.py)):

- Each embeds a `UserDAO`
- `add_*` inserts into both `user` and role tables atomically
- `get_*_by_id` JOINs via `_join_user()` and returns a flat dict
- `SHARED_USER_FIELDS` constant drives update partitioning: shared fields route to `UserDAO.update`, role-specific fields go to the role table

## Other DAOs

| DAO | Table | Notes |
| --- | --- | --- |
| `MembershipDAO` | `membership` | One row per teacher/parent. Students never have a row. Used by `MembershipService` for trial + Stripe sync. `get_by_stripe_customer_id` and `get_by_stripe_subscription_id` are the webhook lookup paths. |
| `SessionDAO` | `session` | Stores minted JWTs for revocation tracking. |
| `ParentInviteDAO` | `parent_invite` | 8-character invite code linking a student to a parent on signup. |
| `EnrollmentDAO` | `enrollment` | Student ↔ period membership. |
| `PeriodDAO` | `period` | Class container with curriculum, vector store, Canvas metadata. |
| `QuestDAO` | `quest` | Quest assignments with rubric, grade, status. |
| `ConversationDAO` | `conversation` | Profile / update assistant chat sessions. |
| `LtgConversationDAO` | `ltg_conversation` | Long-term goal conversation sessions (separate flow from profile). |
| `StudentLongTermGoalDAO` | `student_long_term_goal` | Final per-(student, period) goal record produced from LTG flow. |
| `StudentSkillMasteryDAO` | `student_skill_mastery` | Boolean mastery per (student, period, skill); written by grading orchestrator using `MASTERY_CUTOFF = 0.70`. |
| `AggregatedMetricsDAO` | `aggregated_metrics` | Class-level percentages per skill per week — `% of students who mastered`. |
| `WeekDAO` / `LessonDAO` / `ConceptDAO` / `SkillDAO` / `ConceptSkillDAO` | `week`, `lesson`, `concept`, `skill`, `concept_skill` | Curriculum knowledge graph (Week → Lesson → Concept → Skill). |
| `MaterialFilesDAO` | `material_files` | Uploaded teacher materials per period. |
| `WaitlistDAO` | `pilot_waitlist` | Pilot program waitlist entries. |
| `PasswordResetTokenDAO` | `password_reset_token` | One-shot reset token, hashed before storage. |
| `PasswordResetRateLimitDAO` | `password_reset_rate_limit` | Per-email rate limiting for `/auth/password-reset/request`. |

## Adding a New DAO

1. Create the Supabase table (with `created_at`, `updated_at`, retention column per [.cursor/rules/EduQuest-Compliance.mdc](../../.cursor/rules/EduQuest-Compliance.mdc)).
2. Add the corresponding Pydantic model in `models/`.
3. Subclass `SupabaseBaseDAO`, name the file `<thing>_dao.py`, and expose typed methods (`get_by_*`, `update`, `delete`, etc.).
4. Add a single integration test under `tests/unit/data_access/`.
5. Update this file with the table name and a one-line description.
