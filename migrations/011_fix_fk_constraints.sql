-- ============================================================
-- Migration: 011_fix_fk_constraints.sql
-- Fix FK constraints that still point to student/parent role
-- tables instead of the normalized user table. These were left
-- over from migration 001 (column renames) and 002 (user table).
-- ============================================================

-- Verify actual constraint names before running (optional):
-- SELECT conname, conrelid::regclass, confrelid::regclass
-- FROM pg_constraint
-- WHERE contype = 'f'
--   AND conrelid::regclass::text IN (
--     'quest', 'enrollment', 'ltg_conversation',
--     'student_long_term_goal', 'parent_invite'
--   );

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
