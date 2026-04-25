# Schema FK Discrepancy — Needs Migration

## Problem

Several tables have FK constraints that still point to the `student` or `parent` role tables
instead of the normalized `user` table. This is a leftover from before Migration 002
(`002_user_table_normalization.sql`), which added the `user` table and moved shared fields
into it. The column renames in Migration 001 (`student_id → user_id`, `parent_id → user_id`)
did NOT update the FK targets — only the column names.

`DATA_TABLES.md` documents these as pointing to `user`, but the actual Supabase constraints
still point to `student` / `parent`.

---

## Affected Tables

| Table | Column | Actual FK target | Should be | Constraint name (actual) |
|---|---|---|---|---|
| `quest` | `user_id` | `student.user_id` | `user.user_id` | `individual_quest_student_id_fkey` |
| `enrollment` | `user_id` | `student.user_id` | `user.user_id` | (renamed from `student_id`) |
| `ltg_conversation` | `user_id` | `student.user_id` | `user.user_id` | (renamed from `student_id`) |
| `student_long_term_goal` | `user_id` | `student.user_id` | `user.user_id` | `student_long_term_goal_student_id_fkey` |
| `parent_invite` | `user_id` | `parent.user_id` | `user.user_id` | (renamed from `parent_id`) |

Note: `conversation` and `waitlist` are correctly pointing to `user.user_id` already.

---

## Fix

For each affected table, drop the old FK constraint and add a new one pointing to `user`:

```sql
-- quest
ALTER TABLE quest DROP CONSTRAINT individual_quest_student_id_fkey;
ALTER TABLE quest ADD CONSTRAINT quest_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES "user"(user_id) ON DELETE CASCADE;

-- enrollment (find and replace existing constraint)
ALTER TABLE enrollment DROP CONSTRAINT IF EXISTS enrollment_student_id_fkey;
ALTER TABLE enrollment ADD CONSTRAINT enrollment_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES "user"(user_id) ON DELETE CASCADE;

-- ltg_conversation
ALTER TABLE ltg_conversation DROP CONSTRAINT IF EXISTS ltg_conversation_student_id_fkey;
ALTER TABLE ltg_conversation ADD CONSTRAINT ltg_conversation_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES "user"(user_id) ON DELETE CASCADE;

-- student_long_term_goal
ALTER TABLE student_long_term_goal DROP CONSTRAINT student_long_term_goal_student_id_fkey;
ALTER TABLE student_long_term_goal ADD CONSTRAINT student_long_term_goal_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES "user"(user_id) ON DELETE CASCADE;

-- parent_invite
ALTER TABLE parent_invite DROP CONSTRAINT IF EXISTS parent_invite_parent_id_fkey;
ALTER TABLE parent_invite ADD CONSTRAINT parent_invite_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES "user"(user_id) ON DELETE CASCADE;
```

Run this in the Supabase SQL editor. You can verify the actual constraint names first with:

```sql
SELECT conname, conrelid::regclass, confrelid::regclass
FROM pg_constraint
WHERE contype = 'f'
  AND conrelid::regclass::text IN (
    'quest', 'enrollment', 'ltg_conversation',
    'student_long_term_goal', 'parent_invite'
  );
```

---

## Impact After Fix

Once corrected, integration test setup only needs to insert into `user` (not `student`/`parent`)
for these tables. The test files currently work around this by using `StudentDAO.add_student()`
and `ParentDAO.add_parent()` (which insert into both `user` and the role table). After the
migration runs, those tests can be simplified to use plain `UserDAO._insert()` if desired —
though using the role DAOs is still semantically correct and not harmful.
