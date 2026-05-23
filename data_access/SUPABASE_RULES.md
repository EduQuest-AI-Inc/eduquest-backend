# Supabase Rules Reference

Authoritative source for RLS policies and FK cascade behaviour.
Schema column definitions live in [DATA_TABLES.md](DATA_TABLES.md).

---

## RLS Identity Expression

All policies use `(auth.jwt() -> 'app_metadata' ->> 'username')` — reads the EduQuest username from the Supabase JWT's `app_metadata` object, directly matching `user_id` values.

- Do **not** use `auth.uid()` — casts to UUID, returns null for username IDs.
- Do **not** use `(auth.jwt() ->> 'sub')` — sub is a UUID in Supabase native JWTs, not the username.

---

## RLS Policies by Table

### `user`

| Operation     | Who  |
| ------------- | ---- |
| SELECT        | Self (`user_id = sub`) |
| UPDATE        | Self (`user_id = sub`) |
| INSERT/DELETE | FastAPI only |

### `student`

| Operation     | Who  |
| ------------- | ---- |
| SELECT        | Self (`user_id = sub`) |
| SELECT        | Parent of student (EXISTS parent where sub ∈ `linked_student_ids`) |
| SELECT        | Period owner (EXISTS enrollment JOIN period where `owner_id = sub`) |
| UPDATE        | Self (`user_id = sub`) |
| INSERT/DELETE | FastAPI only |

### `teacher`

| Operation     | Who  |
| ------------- | ---- |
| SELECT        | Self (`user_id = sub`) |
| UPDATE        | Self (`user_id = sub`) |
| INSERT/DELETE | FastAPI only |

### `parent`

| Operation     | Who  |
| ------------- | ---- |
| SELECT        | Self (`user_id = sub`) |
| UPDATE        | Self (`user_id = sub`) |
| INSERT/DELETE | FastAPI only |

### `period`

| Operation     | Who  |
| ------------- | ---- |
| SELECT        | Owner (`owner_id = sub`) |
| SELECT        | Enrolled student (EXISTS enrollment where `user_id = sub`) |
| UPDATE        | Owner (`owner_id = sub`) |
| INSERT        | Any authenticated user |
| DELETE        | Owner (`owner_id = sub`) |

### `enrollment`

| Operation | Who  |
| --------- | ---- |
| SELECT    | Period owner (EXISTS period where `owner_id = sub`) |
| SELECT    | Enrolled student (self — `user_id = sub`) |
| INSERT    | Self only (`user_id = sub` WITH CHECK) |
| DELETE    | Self only (`user_id = sub`) |

### `period_schedule`

| Operation            | Who  |
| -------------------- | ---- |
| SELECT               | Period owner (EXISTS period where `owner_id = sub`) |
| SELECT               | Enrolled student (EXISTS enrollment where `user_id = sub`) |
| INSERT/UPDATE/DELETE | FastAPI only |

### `parent_invite`

| Operation            | Who  |
| -------------------- | ---- |
| SELECT               | Parent creator (`user_id = sub`) — note: `user_id` here is the **parent**, not the student |
| INSERT/UPDATE/DELETE | FastAPI only — invite creation and redemption always go through the service role |

### `week`

| Operation            | Who  |
| -------------------- | ---- |
| SELECT               | Period owner (EXISTS period where `owner_id = sub`) |
| SELECT               | Enrolled student (EXISTS enrollment where `user_id = sub`) |
| SELECT               | Parent (EXISTS parent where sub ∈ `linked_student_ids` AND student enrolled in period) |
| INSERT               | Period owner (WITH CHECK EXISTS period where `owner_id = sub`) |
| UPDATE               | Period owner (USING + WITH CHECK EXISTS period where `owner_id = sub`) |
| DELETE               | Period owner (EXISTS period where `owner_id = sub`) |

### `lesson`

| Operation            | Who  |
| -------------------- | ---- |
| SELECT               | Period owner (EXISTS period where `owner_id = sub`) |
| SELECT               | Enrolled student (EXISTS enrollment where `user_id = sub`) |
| INSERT               | Period owner (WITH CHECK EXISTS period where `owner_id = sub`) |
| UPDATE               | Period owner (USING + WITH CHECK EXISTS period where `owner_id = sub`) |
| DELETE               | Period owner (EXISTS period where `owner_id = sub`) |

### `lesson_pptx`

| Operation     | Who                                                        |
| ------------- | ---------------------------------------------------------- |
| SELECT        | Period owner (EXISTS period where `owner_id = sub`)        |
| SELECT        | Enrolled student (EXISTS enrollment where `user_id = sub`) |
| SELECT        | Parent of enrolled student (EXISTS parent → enrollment)    |
| INSERT/UPDATE | FastAPI only                                               |

### `concept`

| Operation            | Who  |
| -------------------- | ---- |
| SELECT               | Period owner (EXISTS period where `owner_id = sub`) |
| SELECT               | Enrolled student (EXISTS enrollment where `user_id = sub`) |
| INSERT               | Period owner (WITH CHECK EXISTS period where `owner_id = sub`) |
| UPDATE               | Period owner (USING + WITH CHECK EXISTS period where `owner_id = sub`) |
| DELETE               | Period owner (EXISTS period where `owner_id = sub`) |

### `skill`

| Operation            | Who  |
| -------------------- | ---- |
| SELECT               | Period owner (EXISTS period where `owner_id = sub`) |
| SELECT               | Enrolled student (EXISTS enrollment where `user_id = sub`) |
| INSERT               | Period owner (WITH CHECK EXISTS period where `owner_id = sub`) |
| UPDATE               | Period owner (USING + WITH CHECK EXISTS period where `owner_id = sub`) |
| DELETE               | Period owner (EXISTS period where `owner_id = sub`) |

### `concept_skill`

| Operation            | Who  |
| -------------------- | ---- |
| SELECT               | Period owner (EXISTS period where `owner_id = sub`) |
| SELECT               | Enrolled student (EXISTS enrollment where `user_id = sub`) |
| INSERT               | Period owner (WITH CHECK EXISTS period where `owner_id = sub`) |
| DELETE               | Period owner (EXISTS period where `owner_id = sub`) |

### `conversation`

| Operation            | Who  |
| -------------------- | ---- |
| SELECT               | Self (`user_id = sub`) |
| INSERT/UPDATE/DELETE | FastAPI only |

### `ltg_conversation`

| Operation            | Who  |
| -------------------- | ---- |
| SELECT               | The student (self — `user_id = sub`) |
| INSERT/UPDATE/DELETE | FastAPI only |

### `quest`

| Operation     | Who  |
| ------------- | ---- |
| SELECT        | The student (`user_id = sub`) |
| SELECT        | Period owner (EXISTS enrollment JOIN period where `owner_id = sub`) |
| SELECT        | Parent (EXISTS parent where sub ∈ `linked_student_ids`) |
| UPDATE        | Student — `status` column only (enforced at FastAPI layer, not RLS) |
| UPDATE        | Period owner — `grade`/`feedback` columns only (enforced at FastAPI layer, not RLS) |
| INSERT/DELETE | FastAPI only |

### `student_skill_mastery`

Note: PK column is `student_id`, not `user_id`.

| Operation            | Who  |
| -------------------- | ---- |
| SELECT               | The student (`student_id = sub`) |
| SELECT               | Period owner (EXISTS period where `owner_id = sub`) |
| SELECT               | Parent (EXISTS parent where sub ∈ `linked_student_ids` and `student_id` matches) |
| INSERT/UPDATE/DELETE | FastAPI only |

### `aggregated_metrics`

RLS disabled — FastAPI service role only.

### `student_long_term_goal`

| Operation            | Who  |
| -------------------- | ---- |
| SELECT               | The student (`user_id = sub`) |
| SELECT               | Period owner (EXISTS period where `owner_id = sub`) |
| SELECT               | Parent (EXISTS parent where sub ∈ `linked_student_ids` and `user_id` matches) |
| INSERT/UPDATE/DELETE | FastAPI only |

### `session`

| Operation | Who  |
| --------- | ---- |
| SELECT    | Self (`user_id = sub`) |
| DELETE    | Self (`user_id = sub`) |
| INSERT    | FastAPI only — JWT doesn't exist yet at login time |

### `password_reset_token`

RLS disabled — FastAPI service role only.

### `password_reset_rate_limit`

RLS disabled — FastAPI service role only.

### `waitlist`

RLS disabled — public signup list, no per-user scoping needed.

### `membership`

| Operation            | Who  |
| -------------------- | ---- |
| SELECT               | Self (`user_id = sub`) |
| INSERT/UPDATE/DELETE | FastAPI only |

### `marketplace_listing`

RLS disabled — FastAPI service role only.

### `user_feedback`

RLS disabled — FastAPI service role only.

### `material_files`

| Operation            | Who  |
| -------------------- | ---- |
| INSERT/UPDATE/DELETE | FastAPI only |

---

## FK Cascade Rules

Added by migration `018_account_deletion_cascade.sql`. Deleting a `user` row or `period` row atomically removes all owned data.

### On `user` deletion

| Table | Column | Behaviour |
| ----- | ------ | --------- |
| `session` | `user_id` | CASCADE |
| `conversation` | `user_id` | CASCADE |
| `password_reset_token` | `user_id` | CASCADE |
| `user_feedback` | `user_id` | CASCADE |
| `parent_invite` | `user_id` | CASCADE |
| `quest` | `user_id` | CASCADE |
| `student_skill_mastery` | `student_id` | CASCADE |
| `student_long_term_goal` | `user_id` | CASCADE |
| `ltg_conversation` | `user_id` | CASCADE |
| `enrollment` | `user_id` | CASCADE |
| `period` | `owner_id` | CASCADE → triggers all period-child cascades below |
| `waitlist` | `user_id` | SET NULL — preserve waitlist position |
| `student` | `created_by_parent_id` | SET NULL — preserve child account when parent deleted |

Note: `membership.user_id` is **not** cascaded — Stripe must be cancelled explicitly before the row is deleted. See `AccountDeletionService`.

### On `period` deletion (triggered by `period.owner_id` cascade above)

| Table | Column | Behaviour |
| ----- | ------ | --------- |
| `week` | `period_id` | CASCADE |
| `lesson` | `period_id` | CASCADE |
| `lesson_pptx` | `period_id` | CASCADE |
| `concept` | `period_id` | CASCADE |
| `skill` | `period_id` | CASCADE |
| `enrollment` | `period_id` | CASCADE |
| `quest` | `period_id` | CASCADE |
| `student_skill_mastery` | `period_id` | CASCADE |
| `student_long_term_goal` | `period_id` | CASCADE |
| `ltg_conversation` | `period_id` | CASCADE |
| `aggregated_metrics` | `period_id` | CASCADE |
| `marketplace_listing` | `period_id` | CASCADE |

### Helper SQL function

`array_remove_from_linked_students(target_student_id text)` — removes a student ID from `parent.linked_student_ids` for all parent rows that contain it. Called by `ParentDAO.remove_student_link` during account deletion.
