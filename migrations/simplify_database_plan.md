# Simplify Database Plan

Pre-launch audit of all type issues and inconsistencies in the Supabase schema.

---

Note recently guest.instructions was changed from text to jsonb. This was done purposefully in order to store a list of steps. Some of this document was written prior to that knoeledge and is outdated.

## Issues by Priority

#### 4. `user.role` — `text` instead of `user_role` enum

`session.role` uses the `user_role` enum (`"student" | "teacher" | "parent"`), but `user.role` is plain `text`. Both columns store the same values. Without the enum, any string can be written into `user.role`, bypassing DB-level validation.

**Fix:**

```sql
ALTER TABLE "user"
    ALTER COLUMN role TYPE user_role
    USING role::user_role;
```

---

### Low — Data Quality

#### 5. `user.last_login` — stored as `text`

Documented as "ISO timestamp" but the column type is `text`. Timestamp functions (`now() - last_login`, range queries, etc.) cannot be used on it without casting.

**Fix:**

```sql
ALTER TABLE "user"
    ALTER COLUMN last_login TYPE TIMESTAMPTZ
    USING last_login::TIMESTAMPTZ;
```

---

#### 6. `timestamp` vs `timestamptz` — mixed throughout all tables

`user.created_at` is `timestamptz` (correct). Almost every other timestamp column across all tables uses bare `timestamp` (no timezone). Supabase stores everything in UTC, but bare `timestamp` carries no timezone metadata, which causes confusion when reading values.

All timestamp columns should be `timestamptz`.

**Affected columns:**

| Table                       | Column                                             |
| --------------------------- | -------------------------------------------------- |
| `period`                    | `created_at`                                       |
| `period_schedule`           | `created_at`, `last_updated_at`                    |
| `enrollment`                | `enrolled_at`                                      |
| `parent_invite`             | `expires_at`, `created_at`                         |
| `quest`                     | `created_at`, `due_date`, `last_updated_at`        |
| `student_skill_mastery`     | `updated_at`                                       |
| `aggregated_metrics`        | `updated_at`                                       |
| `student_long_term_goal`    | `updated_at`                                       |
| `conversation`              | `created_at`                                       |
| `ltg_conversation`          | `created_at`                                       |
| `session`                   | `expires_at`                                       |
| `password_reset_token`      | `created_at`, `expires_at`, `used_at`, `burned_at` |
| `password_reset_rate_limit` | `expires_at`                                       |
| `waitlist`                  | `joined_at`                                        |
| `parent`                    | `vpc_verified_at`                                  |

**Fix (repeat for each column):**

```sql
ALTER TABLE <table> ALTER COLUMN <column> TYPE TIMESTAMPTZ USING <column> AT TIME ZONE 'UTC';
```

## Summary Table

| #   | Issue                                                             | Table.Column                          | Severity | Action                                     |
| --- | ----------------------------------------------------------------- | ------------------------------------- | -------- | ------------------------------------------ |
| 1   | `instructions` stored as JSON object, not text                    | `quest.instructions`                  | High     | Migration to confirm/fix type + clean data |
| 2   | `quest_enabled_weeks` docs said `integer` (confirmed `integer[]`) | `period_schedule.quest_enabled_weeks` | None     | DATA_TABLES.md updated — done              |
| 3   | No PK constraint                                                  | `aggregated_metrics`                  | Medium   | Add composite PK                           |
| 4   | `role` uses `text` not `user_role` enum                           | `user.role`                           | Medium   | Migrate to enum                            |
| 5   | `last_login` stored as `text`                                     | `user.last_login`                     | Low      | Migrate to `timestamptz`                   |
| 6   | `timestamp` instead of `timestamptz`                              | 15+ columns across 14 tables          | Low      | Migrate all to `timestamptz`               |
| 7   | `string[]` in docs (should be `text[]`)                           | docs only                             | None     | DATA_TABLES.md updated — done              |

---

## Migration File

All schema changes above should be written as `008_simplify_types.sql` once confirmed against the live Supabase instance. Confirm the actual column types in Supabase Dashboard > Table Editor before running any `ALTER COLUMN TYPE` statements — if the type already matches the target, skip that statement.
