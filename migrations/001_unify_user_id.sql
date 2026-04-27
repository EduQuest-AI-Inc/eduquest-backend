-- Migration 001: Unify role-specific IDs to user_id
--
-- Renames student_id, teacher_id, parent_id PKs and all FK references
-- to the single column name user_id. The session, conversation, and
-- password_reset_token tables already use user_id and are unchanged.

-- User tables (PK rename)
ALTER TABLE student RENAME COLUMN student_id TO user_id;
ALTER TABLE teacher RENAME COLUMN teacher_id TO user_id;
ALTER TABLE parent RENAME COLUMN parent_id TO user_id;
ALTER TABLE parent RENAME COLUMN linked_student_ids TO linked_user_ids;

-- FK tables
ALTER TABLE enrollment RENAME COLUMN student_id TO user_id;
ALTER TABLE individual_quest RENAME COLUMN student_id TO user_id;
ALTER TABLE weekly_quest RENAME COLUMN student_id TO user_id;
ALTER TABLE ltg_conversation RENAME COLUMN student_id TO user_id;
ALTER TABLE period_schedule RENAME COLUMN teacher_id TO user_id;
ALTER TABLE parent_invite RENAME COLUMN parent_id TO user_id;

-- student_long_term_goal table (referenced in StudentDAO.update_long_term_goal)
ALTER TABLE student_long_term_goal RENAME COLUMN student_id TO user_id;

-- Remove deprecated backward-compat aliases from period table
ALTER TABLE period DROP COLUMN IF EXISTS teacher_id;
ALTER TABLE period DROP COLUMN IF EXISTS parent_id;
