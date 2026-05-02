# Simplify Database Plan

Pre-launch audit of all type issues and inconsistencies in the Supabase schema.

---

Note recently guest.instructions was changed from text to jsonb. This was done purposefully in order to store a list of steps. Some of this document was written prior to that knoeledge and is outdated.

## Issues by Priority

### High — Live Bugs

#### 1. `quest.instructions` — wrong column type in production

DATA_TABLES.md documents this as `text`, but the frontend is receiving a parsed object `{step, text}` at runtime, which means the actual Supabase column is `json` or `jsonb`. Supabase never parses a `text` column as JSON — if an object is coming back, the column is not `text`.

**Why `text` is correct here:** `instructions` is a blob of prose/numbered text meant to be displayed as-is. `jsonb` is valuable when you need to query _into_ the structure (e.g. `WHERE instructions->>'step' = '3'`), which never happens for instructions. `text` is simpler, has no parsing overhead, and can't accidentally receive a structured object — if you write a dict to a `text` column, Supabase errors or stores a literal string, both of which are easier to debug than silently storing a parsed object. Compare: `rubric` and `grade` legitimately use `jsonb` because the code reads fields out of them. `instructions` is just a string you display.

**Fix:** Confirm the actual column type in Supabase. If it is `json`/`jsonb`, either:

- Convert it to `text` and extract the string content from any stored objects, or
- Accept `jsonb` and always write plain strings into it going forward (Supabase stores plain strings in jsonb fine)

The simplest path is converting to `text` and cleaning up any rows where the stored value is a JSON object:

```sql
-- Convert instructions from jsonb to text, extracting the string value where needed
ALTER TABLE quest
    ALTER COLUMN instructions TYPE TEXT
    USING CASE
        WHEN instructions IS NULL THEN NULL
        WHEN jsonb_typeof(instructions::jsonb) = 'object' THEN instructions::jsonb->>'text'
        WHEN jsonb_typeof(instructions::jsonb) = 'array'  THEN (
            SELECT string_agg(elem->>'text', E'\n')
            FROM jsonb_array_elements(instructions::jsonb) AS elem
        )
        ELSE instructions::text
    END;
```

> Note: run this only after confirming the actual column type. If the column is already `text`, skip the ALTER and only run a data-fix UPDATE.

---

#### 2. `period_schedule.quest_enabled_weeks` — documented as `integer`, actually `integer[]`

DATA_TABLES.md says `integer` with a confused "Bitmask or count" note. The Pydantic model declares `List[int]` and the service code does `if week_num in quest_enabled_weeks` — array membership, not bitwise. The actual column must be `integer[]`. If it was ever created as a plain `integer`, quest generation silently breaks.

**Fix:** Confirm the actual column type. If it is `integer`, migrate it:

```sql
-- Add a new array column, populate it, then swap
ALTER TABLE period_schedule ADD COLUMN quest_enabled_weeks_new INTEGER[];
UPDATE period_schedule SET quest_enabled_weeks_new = ARRAY[quest_enabled_weeks] WHERE quest_enabled_weeks IS NOT NULL;
ALTER TABLE period_schedule DROP COLUMN quest_enabled_weeks;
ALTER TABLE period_schedule RENAME COLUMN quest_enabled_weeks_new TO quest_enabled_weeks;
```

If the column is already `integer[]`, update DATA_TABLES.md only.

---

### Medium — Correctness / Integrity

#### 3. `aggregated_metrics` — no PK constraint

DATA_TABLES.md's quick-reference lists `(period_id, week, skill_name)` as the key, but the table schema section never marks any column as PK. Without a constraint, duplicate rows are silently allowed.

**Fix:**

```sql
ALTER TABLE aggregated_metrics
    ADD CONSTRAINT aggregated_metrics_pkey PRIMARY KEY (period_id, week, skill_name);
```

---

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

---

### None — Documentation Only

#### 7. `string[]` notation throughout DATA_TABLES.md

PostgreSQL has no `string[]` type; the correct notation is `text[]`. The actual DB columns are already `text[]` — this is a docs error only.

**Affected fields:** `student.strength`, `student.weakness`, `student.interest`, `parent.linked_student_ids`, `period.file_url`

**Fix:** Update DATA_TABLES.md to use `text[]` instead of `string[]`.

---

## Summary Table

| #   | Issue                                              | Table.Column                          | Severity | Action                                     |
| --- | -------------------------------------------------- | ------------------------------------- | -------- | ------------------------------------------ |
| 1   | `instructions` stored as JSON object, not text     | `quest.instructions`                  | High     | Migration to confirm/fix type + clean data |
| 2   | `quest_enabled_weeks` is `integer` not `integer[]` | `period_schedule.quest_enabled_weeks` | High     | Confirm actual type; migrate if needed     |
| 3   | No PK constraint                                   | `aggregated_metrics`                  | Medium   | Add composite PK                           |
| 4   | `role` uses `text` not `user_role` enum            | `user.role`                           | Medium   | Migrate to enum                            |
| 5   | `last_login` stored as `text`                      | `user.last_login`                     | Low      | Migrate to `timestamptz`                   |
| 6   | `timestamp` instead of `timestamptz`               | 15+ columns across 14 tables          | Low      | Migrate all to `timestamptz`               |
| 7   | `string[]` in docs (should be `text[]`)            | docs only                             | None     | Update DATA_TABLES.md                      |

---

## Migration File

All schema changes above should be written as `008_simplify_types.sql` once confirmed against the live Supabase instance. Confirm the actual column types in Supabase Dashboard > Table Editor before running any `ALTER COLUMN TYPE` statements — if the type already matches the target, skip that statement.
