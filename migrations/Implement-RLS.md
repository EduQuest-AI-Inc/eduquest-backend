# Supabase Row Level Security

---

THIS MIGRATION HAS BEEN COMPLETED May 1st, 2026

## Is This Feasible, Or Should You Just Do It In Application Code?

**Short answer: RLS is still worth doing, but its role has changed.** Every frontend route now proxies through FastAPI — zero routes query Supabase directly. FastAPI enforces all authorization. RLS is therefore pure defense-in-depth: a database-level backstop that catches bugs in FastAPI route handlers and makes the intended access model explicit in the schema.

**Why it is still the right call:**

- FastAPI uses the service role key, which bypasses RLS entirely. Any authorization bug in a FastAPI handler — a missing ownership check, a wrong filter — results in a data leak with no fallback. RLS closes that gap.
- The Supabase client utilities (`lib/supabase/server.ts`, `lib/supabase/browser.ts`) exist in the frontend but are currently unused. If any future route uses them without going through FastAPI, RLS policies are the only thing standing between that route and the raw database.
- RLS also serves as machine-readable documentation of the intended access model, co-located with the schema.

**What changed:** The prerequisite work in the previous version of this plan — migrating 17 frontend routes to a `createUserClient()` helper and changing the JWT `role` claim to `"authenticated"` — is **no longer needed**. All traffic already goes through FastAPI. The JWT `role` claim change would still be required if direct Supabase queries are ever added, but that is a future concern. For now, skip Phase 1 of the old plan entirely and go straight to the SQL migration.

---

## Implementation Plan

### Authorization architecture

RLS is the **second layer** of authorization, acting as a database-level backstop:

- **FastAPI backend** — the primary enforcement layer for all routes. FastAPI validates JWTs, checks ownership, and filters results. Uses `SUPABASE_SERVICE_ROLE_KEY`, which bypasses RLS by design — this is intentional.
- **Supabase RLS (this step)** — defense-in-depth. Catches any row that FastAPI's authorization checks fail to filter. Not the primary enforcement layer for any current route, but a critical safety net.

### Identity expression

All policies use `(auth.jwt() ->> 'sub')`. This reads the `sub` claim from the JWT as raw text. It directly equals `user_id` values (which are usernames like `"johnsmith123"`, not UUIDs). **Do not use `auth.uid()`** — it casts `sub` to UUID and silently returns null for username-format IDs.

### Why `auth.uid()` cannot be used

`auth.uid()` is defined in Postgres as `returns uuid`. Your `user_id` values are user-chosen usernames. The cast silently returns `null` and every policy that uses `auth.uid()` will block all rows.

---

### Phase 1: One prerequisite — verify the Supabase JWT secret

Since all traffic goes through FastAPI (service role, bypasses RLS), the JWT `role` claim change is **not required** before writing policies. The only prerequisite is confirming the secrets match so that Supabase can validate JWTs if a user-scoped client is ever introduced.

Go to Supabase dashboard → Settings → API → JWT Secret. Confirm the value equals `JWT_SECRET_KEY` in the backend `.env`. Update Supabase's secret to match yours if they differ — not the other way around, as changing `JWT_SECRET_KEY` invalidates all active sessions.

### Phase 2: SQL migration

Run **one migration file** after the Phase 1 prerequisite is confirmed. The file must be idempotent (`if not exists`, `create policy if not exists`). Order within the file:

1. Enable RLS on all tables
2. Create policies (tables with no cross-table dependencies first, then tables that reference others)
3. Add missing indexes
4. Add comments for excluded tables

---

### Which tables get RLS

**Apply RLS:**

| Table                    | Reason                                                               |
| ------------------------ | -------------------------------------------------------------------- |
| `user`                   | PII, hashed passwords                                                |
| `student`                | Educational profile data                                             |
| `teacher`                | Role data, Canvas API keys                                           |
| `parent`                 | Contains `linked_student_ids`                                        |
| `period`                 | Teacher-owned class data                                             |
| `period_schedule`        | Teacher-owned schedule                                               |
| `enrollment`             | Student-period membership                                            |
| `quest`                  | Per-student assignment data and grades (formerly `individual_quest`) |
| `student_skill_mastery`  | Per-student skill scores                                             |
| `conversation`           | AI chat history                                                      |
| `student_long_term_goal` | Per-student goal text                                                |
| `ltg_conversation`       | OpenAI conversation IDs per student                                  |
| `parent_invite`          | Single-use invite codes                                              |
| `session`                | Auth tokens                                                          |

**Do NOT apply RLS:**

| Table                       | Reason                                         |
| --------------------------- | ---------------------------------------------- |
| `waitlist`                  | Public signup list; no per-user scoping needed |
| `password_reset_token`      | FastAPI service role only; never from frontend |
| `password_reset_rate_limit` | FastAPI service role only                      |
| `aggregated_metrics`        | FastAPI service role only                      |

---

### Access rules per table

Identity expression throughout: `(auth.jwt() ->> 'sub')` — returns the `sub` claim as text, directly equals `user_id`.

#### `user`

| Operation | Who                 | Condition                          |
| --------- | ------------------- | ---------------------------------- |
| SELECT    | Self                | `user_id = (auth.jwt() ->> 'sub')` |
| UPDATE    | Self                | `user_id = (auth.jwt() ->> 'sub')` |
| INSERT    | Nobody via frontend | FastAPI only                       |
| DELETE    | Nobody via frontend | FastAPI only                       |

#### `student`

| Operation     | Who                 | Condition                                          |
| ------------- | ------------------- | -------------------------------------------------- |
| SELECT        | Self                | `user_id = (auth.jwt() ->> 'sub')`                 |
| SELECT        | Parent of student   | EXISTS parent where sub is in `linked_student_ids` |
| SELECT        | Period owner        | EXISTS enrollment+period where `owner_id = sub`    |
| UPDATE        | Self                | `user_id = (auth.jwt() ->> 'sub')`                 |
| INSERT/DELETE | Nobody via frontend | FastAPI only                                       |

#### `teacher`

| Operation     | Who                 | Condition                          |
| ------------- | ------------------- | ---------------------------------- |
| SELECT        | Self                | `user_id = (auth.jwt() ->> 'sub')` |
| UPDATE        | Self                | `user_id = (auth.jwt() ->> 'sub')` |
| INSERT/DELETE | Nobody via frontend | FastAPI only                       |

#### `parent`

| Operation     | Who                 | Condition                          |
| ------------- | ------------------- | ---------------------------------- |
| SELECT        | Self                | `user_id = (auth.jwt() ->> 'sub')` |
| UPDATE        | Self                | `user_id = (auth.jwt() ->> 'sub')` |
| INSERT/DELETE | Nobody via frontend | FastAPI only                       |

#### `period`

| Operation     | Who                 | Condition                                                       |
| ------------- | ------------------- | --------------------------------------------------------------- |
| SELECT        | Owner (teacher)     | `owner_id = (auth.jwt() ->> 'sub')`                             |
| SELECT        | Enrolled student    | EXISTS enrollment where `user_id = sub` and `period_id` matches |
| UPDATE        | Owner               | `owner_id = (auth.jwt() ->> 'sub')`                             |
| INSERT/DELETE | Nobody via frontend | FastAPI only                                                    |

#### `period_schedule`

| Operation | Who                 | Condition                                                    |
| --------- | ------------------- | ------------------------------------------------------------ |
| SELECT    | Period owner        | EXISTS period where `owner_id = sub` and `period_id` matches |
| INSERT    | Period owner        | Same (WITH CHECK)                                            |
| UPDATE    | Period owner        | Same                                                         |
| DELETE    | Nobody via frontend | FastAPI only                                                 |

#### `enrollment`

| Operation | Who              | Condition                            |
| --------- | ---------------- | ------------------------------------ |
| SELECT    | Period owner     | EXISTS period where `owner_id = sub` |
| SELECT    | Enrolled student | `user_id = (auth.jwt() ->> 'sub')`   |
| INSERT    | Self only        | `user_id = (auth.jwt() ->> 'sub')`   |
| DELETE    | Enrolled student | `user_id = (auth.jwt() ->> 'sub')`   |

#### `quest` (formerly `individual_quest`)

| Operation     | Who                           | Condition                                          |
| ------------- | ----------------------------- | -------------------------------------------------- |
| SELECT        | The student                   | `user_id = (auth.jwt() ->> 'sub')`                 |
| SELECT        | Period owner                  | EXISTS enrollment+period where `owner_id = sub`    |
| SELECT        | Parent                        | EXISTS parent where sub is in `linked_student_ids` |
| UPDATE        | Period owner (grade/feedback) | EXISTS enrollment+period where `owner_id = sub`    |
| UPDATE        | Student (status)              | `user_id = (auth.jwt() ->> 'sub')`                 |
| INSERT/DELETE | Nobody via frontend           | FastAPI only                                       |

Note: Column-level restriction (student can only update `status`, teacher only `grade`/`feedback`) is enforced at the FastAPI layer, not RLS. RLS only controls row-level access.

#### `student_skill_mastery`

| Operation            | Who                 | Condition                                                                   |
| -------------------- | ------------------- | --------------------------------------------------------------------------- |
| SELECT               | The student         | `student_id = (auth.jwt() ->> 'sub')`                                       |
| SELECT               | Period owner        | EXISTS period where `owner_id = sub` and `period_id` matches                |
| SELECT               | Parent              | EXISTS parent where sub is in `linked_student_ids` and `student_id` matches |
| INSERT/UPDATE/DELETE | Nobody via frontend | FastAPI only                                                                |

Note: The PK column is `student_id`, not `user_id`. The identity expression compares against `student_id`.

#### `conversation`

| Operation            | Who                 | Condition                          |
| -------------------- | ------------------- | ---------------------------------- |
| SELECT               | Self                | `user_id = (auth.jwt() ->> 'sub')` |
| INSERT/UPDATE/DELETE | Nobody via frontend | FastAPI only                       |

#### `student_long_term_goal`

| Operation            | Who                 | Condition                                                                |
| -------------------- | ------------------- | ------------------------------------------------------------------------ |
| SELECT               | The student         | `user_id = (auth.jwt() ->> 'sub')`                                       |
| SELECT               | Period owner        | EXISTS period where `owner_id = sub` and `period_id` matches             |
| SELECT               | Parent              | EXISTS parent where sub is in `linked_student_ids` and `user_id` matches |
| INSERT/UPDATE/DELETE | Nobody via frontend | FastAPI only                                                             |

#### `ltg_conversation`

| Operation            | Who                 | Condition                          |
| -------------------- | ------------------- | ---------------------------------- |
| SELECT               | The student         | `user_id = (auth.jwt() ->> 'sub')` |
| INSERT/UPDATE/DELETE | Nobody via frontend | FastAPI only                       |

#### `parent_invite`

| Operation            | Who                 | Condition                          |
| -------------------- | ------------------- | ---------------------------------- |
| SELECT               | The parent          | `user_id = (auth.jwt() ->> 'sub')` |
| INSERT/UPDATE/DELETE | Nobody via frontend | FastAPI only                       |

**Important:** `parent_invite.user_id` is the **parent's** user ID (the invite creator), not the student's. Students never query this table — redemption goes through FastAPI service role, which looks up the invite by code using the service role key.

#### `session`

| Operation | Who                 | Condition                                          |
| --------- | ------------------- | -------------------------------------------------- |
| SELECT    | Self                | `user_id = (auth.jwt() ->> 'sub')`                 |
| DELETE    | Self                | `user_id = (auth.jwt() ->> 'sub')`                 |
| INSERT    | Nobody via frontend | FastAPI only (JWT doesn't exist yet at login time) |

---

### Phase 3: Post-deployment verification

Run each test using the Supabase SQL editor impersonation pattern (Section 3 includes the full test block). Verify:

1. FastAPI service role queries still work (run a known backend operation, confirm no 403s)
2. Each user role sees only their expected rows
3. No cross-user data leakage

---

## SQL Policies (Grouped by Table)

This is the complete migration file. Run it as a single transaction in the Supabase SQL editor or via the CLI.

```sql
-- ============================================================
-- Migration: 008_rls_policies.sql
-- Enable Row Level Security on all sensitive tables.
-- Identity expression: (auth.jwt() ->> 'sub') reads the JWT
-- 'sub' claim as text, directly matching user_id values.
-- Do NOT use auth.uid() — it casts to UUID and returns null
-- for username-format user IDs.
--
-- FastAPI backend uses SUPABASE_SERVICE_ROLE_KEY and bypasses
-- all RLS policies by design. These policies only fire for
-- direct frontend Supabase queries using the anon key + user JWT.
-- ============================================================

-- ============================================================
-- TABLES EXPLICITLY EXCLUDED FROM RLS
-- ============================================================
-- waitlist          — public signup, no per-user scoping
-- password_reset_token      — FastAPI service role only
-- password_reset_rate_limit — FastAPI service role only
-- aggregated_metrics        — FastAPI service role only
-- ============================================================


-- ============================================================
-- TABLE: user
-- ============================================================
alter table "user" enable row level security;

create policy "user: self select"
  on "user"
  for select
  using (user_id = (auth.jwt() ->> 'sub'));

create policy "user: self update"
  on "user"
  for update
  using (user_id = (auth.jwt() ->> 'sub'));


-- ============================================================
-- TABLE: student
-- ============================================================
alter table student enable row level security;

create policy "student: self select"
  on student
  for select
  using (user_id = (auth.jwt() ->> 'sub'));

create policy "student: parent select"
  on student
  for select
  using (
    exists (
      select 1 from parent
      where parent.user_id = (auth.jwt() ->> 'sub')
        and student.user_id = any(parent.linked_student_ids)
    )
  );

create policy "student: period owner select"
  on student
  for select
  using (
    exists (
      select 1 from enrollment e
      join period p on p.period_id = e.period_id
      where e.user_id = student.user_id
        and p.owner_id = (auth.jwt() ->> 'sub')
    )
  );

create policy "student: self update"
  on student
  for update
  using (user_id = (auth.jwt() ->> 'sub'));


-- ============================================================
-- TABLE: teacher
-- ============================================================
alter table teacher enable row level security;

create policy "teacher: self select"
  on teacher
  for select
  using (user_id = (auth.jwt() ->> 'sub'));

create policy "teacher: self update"
  on teacher
  for update
  using (user_id = (auth.jwt() ->> 'sub'));


-- ============================================================
-- TABLE: parent
-- ============================================================
alter table parent enable row level security;

create policy "parent: self select"
  on parent
  for select
  using (user_id = (auth.jwt() ->> 'sub'));

create policy "parent: self update"
  on parent
  for update
  using (user_id = (auth.jwt() ->> 'sub'));


-- ============================================================
-- TABLE: period
-- ============================================================
alter table period enable row level security;

create policy "period: owner select"
  on period
  for select
  using (owner_id = (auth.jwt() ->> 'sub'));

create policy "period: enrolled student select"
  on period
  for select
  using (
    exists (
      select 1 from enrollment e
      where e.period_id = period.period_id
        and e.user_id = (auth.jwt() ->> 'sub')
    )
  );

create policy "period: owner update"
  on period
  for update
  using (owner_id = (auth.jwt() ->> 'sub'));


-- ============================================================
-- TABLE: period_schedule
-- ============================================================
alter table period_schedule enable row level security;

create policy "period_schedule: owner select"
  on period_schedule
  for select
  using (
    exists (
      select 1 from period p
      where p.period_id = period_schedule.period_id
        and p.owner_id = (auth.jwt() ->> 'sub')
    )
  );

create policy "period_schedule: owner insert"
  on period_schedule
  for insert
  with check (
    exists (
      select 1 from period p
      where p.period_id = period_schedule.period_id
        and p.owner_id = (auth.jwt() ->> 'sub')
    )
  );

create policy "period_schedule: owner update"
  on period_schedule
  for update
  using (
    exists (
      select 1 from period p
      where p.period_id = period_schedule.period_id
        and p.owner_id = (auth.jwt() ->> 'sub')
    )
  );


-- ============================================================
-- TABLE: enrollment
-- ============================================================
alter table enrollment enable row level security;

create policy "enrollment: period owner select"
  on enrollment
  for select
  using (
    exists (
      select 1 from period p
      where p.period_id = enrollment.period_id
        and p.owner_id = (auth.jwt() ->> 'sub')
    )
  );

create policy "enrollment: enrolled student select"
  on enrollment
  for select
  using (user_id = (auth.jwt() ->> 'sub'));

-- Student self-enrollment only — user_id must match the caller's sub.
create policy "enrollment: self insert"
  on enrollment
  for insert
  with check (user_id = (auth.jwt() ->> 'sub'));

create policy "enrollment: student delete"
  on enrollment
  for delete
  using (user_id = (auth.jwt() ->> 'sub'));


-- ============================================================
-- TABLE: quest  (formerly individual_quest, renamed migration 004)
-- Column-level restriction (student → status only, teacher →
-- grade/feedback only) is enforced at the FastAPI layer, not here.
-- ============================================================
alter table quest enable row level security;

create policy "quest: student select"
  on quest
  for select
  using (user_id = (auth.jwt() ->> 'sub'));

create policy "quest: period owner select"
  on quest
  for select
  using (
    exists (
      select 1 from enrollment e
      join period p on p.period_id = e.period_id
      where e.user_id = quest.user_id
        and p.owner_id = (auth.jwt() ->> 'sub')
    )
  );

create policy "quest: parent select"
  on quest
  for select
  using (
    exists (
      select 1 from parent
      where parent.user_id = (auth.jwt() ->> 'sub')
        and quest.user_id = any(parent.linked_student_ids)
    )
  );

create policy "quest: student update"
  on quest
  for update
  using (user_id = (auth.jwt() ->> 'sub'));

create policy "quest: period owner update"
  on quest
  for update
  using (
    exists (
      select 1 from enrollment e
      join period p on p.period_id = e.period_id
      where e.user_id = quest.user_id
        and p.owner_id = (auth.jwt() ->> 'sub')
    )
  );


-- ============================================================
-- TABLE: student_skill_mastery
-- PK column is student_id (not user_id) — identity expression
-- compares against student_id.
-- ============================================================
alter table student_skill_mastery enable row level security;

create policy "student_skill_mastery: student select"
  on student_skill_mastery
  for select
  using (student_id = (auth.jwt() ->> 'sub'));

create policy "student_skill_mastery: period owner select"
  on student_skill_mastery
  for select
  using (
    exists (
      select 1 from period p
      where p.period_id = student_skill_mastery.period_id
        and p.owner_id = (auth.jwt() ->> 'sub')
    )
  );

create policy "student_skill_mastery: parent select"
  on student_skill_mastery
  for select
  using (
    exists (
      select 1 from parent
      where parent.user_id = (auth.jwt() ->> 'sub')
        and student_skill_mastery.student_id = any(parent.linked_student_ids)
    )
  );


-- ============================================================
-- TABLE: conversation
-- ============================================================
alter table conversation enable row level security;

create policy "conversation: self select"
  on conversation
  for select
  using (user_id = (auth.jwt() ->> 'sub'));


-- ============================================================
-- TABLE: student_long_term_goal
-- ============================================================
alter table student_long_term_goal enable row level security;

create policy "student_long_term_goal: student select"
  on student_long_term_goal
  for select
  using (user_id = (auth.jwt() ->> 'sub'));

create policy "student_long_term_goal: period owner select"
  on student_long_term_goal
  for select
  using (
    exists (
      select 1 from period p
      where p.period_id = student_long_term_goal.period_id
        and p.owner_id = (auth.jwt() ->> 'sub')
    )
  );

create policy "student_long_term_goal: parent select"
  on student_long_term_goal
  for select
  using (
    exists (
      select 1 from parent
      where parent.user_id = (auth.jwt() ->> 'sub')
        and student_long_term_goal.user_id = any(parent.linked_student_ids)
    )
  );


-- ============================================================
-- TABLE: ltg_conversation
-- ============================================================
alter table ltg_conversation enable row level security;

create policy "ltg_conversation: student select"
  on ltg_conversation
  for select
  using (user_id = (auth.jwt() ->> 'sub'));


-- ============================================================
-- TABLE: parent_invite
-- user_id = the parent who created the invite (NOT the student).
-- Invite creation and redemption go through FastAPI service role.
-- Students never query this table directly.
-- ============================================================
alter table parent_invite enable row level security;

create policy "parent_invite: parent select"
  on parent_invite
  for select
  using (user_id = (auth.jwt() ->> 'sub'));


-- ============================================================
-- TABLE: session
-- INSERT omitted: JWT does not exist yet at login time;
-- session creation goes through FastAPI service role.
-- ============================================================
alter table session enable row level security;

create policy "session: self select"
  on session
  for select
  using (user_id = (auth.jwt() ->> 'sub'));

create policy "session: self delete"
  on session
  for delete
  using (user_id = (auth.jwt() ->> 'sub'));


-- ============================================================
-- INDEXES (add any missing; idx_enrollment_user_id,
-- idx_period_owner_id, idx_quest_user_period, and
-- idx_conversation_user_id already exist from migration 004)
-- ============================================================
create index if not exists idx_quest_user_id
  on quest(user_id);

create index if not exists idx_quest_period_id
  on quest(period_id);

-- GIN index for parent.linked_student_ids array lookups.
-- At current scale (1-5 children per parent) this is optional,
-- but add it now to avoid a future hot migration.
create index if not exists idx_parent_linked_student_ids
  on parent using gin(linked_student_ids);
```

### Testing a policy in the Supabase SQL editor

```sql
-- Impersonate a student:
select set_config(
  'request.jwt.claims',
  '{"sub": "johnsmith123", "role": "authenticated", "app_role": "student"}',
  true
);
select * from quest;
-- Must return only rows where user_id = 'johnsmith123'

-- Impersonate a teacher:
select set_config(
  'request.jwt.claims',
  '{"sub": "msteacher456", "role": "authenticated", "app_role": "teacher"}',
  true
);
select * from quest;
-- Must return only quests for students enrolled in msteacher456's periods

-- Impersonate a parent:
select set_config(
  'request.jwt.claims',
  '{"sub": "parentuser789", "role": "authenticated", "app_role": "parent"}',
  true
);
select * from student;
-- Must return only students whose user_id is in parent.linked_student_ids
-- where parent.user_id = 'parentuser789'

-- Confirm service role still bypasses RLS (run as service role connection):
select * from quest;
-- Must return all rows
```

---

## Required Migrations

Execute in this exact order. Do not run step N+1 until step N is verified.

| Order | Type   | What                                                                 | Location                            |
| ----- | ------ | -------------------------------------------------------------------- | ----------------------------------- |
| 1     | Manual | Verify Supabase JWT secret matches `JWT_SECRET_KEY`                  | Supabase dashboard → Settings → API |
| 2     | SQL    | Run `008_rls_policies.sql` in Supabase SQL editor                    | SQL Policies section above          |
| 3     | Verify | Run SQL editor impersonation tests for each role                     | Testing block in SQL Policies above |
| 4     | Verify | Smoke-test FastAPI routes to confirm service role bypass still works | Postman / staging                   |

---

## Risks and Validation Checklist

### High-severity risks

**Risk 1: Supabase JWT secret mismatch**

- Symptom: Any future direct Supabase query using a user JWT returns 401, while FastAPI still works fine.
- Check: Compare `JWT_SECRET_KEY` in `.env` against Supabase dashboard JWT secret character-for-character. Secrets are case-sensitive.

**Risk 2: `linked_student_ids` column name**

- Symptom: Parent policies return no rows. Run `select linked_student_ids from parent limit 1` to confirm the column exists with this exact name.

**Risk 3: `student_skill_mastery` uses `student_id` not `user_id`**

- Symptom: Students cannot see their own skill mastery rows after RLS is enabled.
- Check: Confirm the policy uses `student_id = (auth.jwt() ->> 'sub')`, not `user_id`.

**Risk 4: RLS policies are defense-in-depth only — FastAPI is authoritative**

- Since all traffic goes through FastAPI (service role), RLS policies never fire in normal operation. Any authorization bug in a FastAPI route handler will result in a leak that RLS does **not** catch, because service role bypasses all policies. RLS only protects against someone bypassing FastAPI and hitting Supabase directly with a user JWT.

**Risk 5: Future direct Supabase queries added without enabling user-scoped client**

- If a developer adds a route that uses `createServerClient()` (service role) and queries Supabase directly, RLS will not fire. The Supabase client utilities in `lib/supabase/` must use `createUserClient(jwt)` (anon key + user JWT) for RLS to be meaningful. Any new direct Supabase route should use that pattern, and if added, the JWT `role` claim must be changed from `"student"|"teacher"|"parent"` to `"authenticated"` (with `app_role` carrying the actual role) before Supabase will evaluate policies.

### Validation checklist

**Pre-deployment:**

- [ ] `JWT_SECRET_KEY` in `.env` equals Supabase dashboard JWT secret (character-for-character, case-sensitive)

**Post-SQL-migration:**

- [ ] Student sees only their own rows in `quest`, `student`, `enrollment`, `conversation`
- [ ] Teacher sees enrolled students' rows in `quest`, `student`, `student_skill_mastery`
- [ ] Parent sees linked students' rows in `student`, `quest`, `student_skill_mastery`
- [ ] Student cannot see another student's `quest` rows
- [ ] Teacher cannot see quests from a student not in their period
- [ ] Parent cannot see a student not in `linked_student_ids`
- [ ] FastAPI backend routes return correct data (service role bypass confirmed)
- [ ] `student_skill_mastery` student policy uses `student_id`, not `user_id`
- [ ] `parent.linked_student_ids` column exists (not `linked_user_ids`)

**Performance:**

- [ ] `idx_quest_user_id` exists on `quest`
- [ ] `idx_quest_period_id` exists on `quest`
- [ ] `idx_parent_linked_student_ids` GIN index exists on `parent`
- [ ] `idx_enrollment_user_id` exists (migration 004)
- [ ] `idx_period_owner_id` exists (migration 004)
- [ ] `idx_quest_user_period` exists (migration 004)

---

## What We Are NOT Doing

- Using `auth.uid()` — it casts `sub` to UUID and silently returns null for username-format user IDs
- Changing the FastAPI service role key setup — FastAPI bypassing RLS is intentional; RLS is defense-in-depth only
- Changing the JWT `role` claim from `"student"|"teacher"|"parent"` to `"authenticated"` — this would be required if direct Supabase queries are added from the frontend, but no such routes exist today
- Writing RLS for `waitlist`, `password_reset_token`, `password_reset_rate_limit`, `aggregated_metrics`
- Enforcing write rate limits via RLS — that stays in FastAPI
- Restricting which columns can be updated via RLS — column-level restrictions stay in FastAPI route handlers
- Using the `weekly_quest` table — it was dropped in migration 004
