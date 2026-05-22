-- Migration 018: Add ON DELETE CASCADE / SET NULL for account deletion
-- Deleting a user row automatically removes all owned data in one atomic operation.
-- Deleting a period row (triggered by owner_id cascade) cleans up all period children.

-- ─── Cascades from user deletion ────────────────────────────────────────────

ALTER TABLE session
  DROP CONSTRAINT IF EXISTS session_user_id_fkey,
  ADD CONSTRAINT session_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES "user"(user_id) ON DELETE CASCADE;

ALTER TABLE conversation
  DROP CONSTRAINT IF EXISTS conversation_user_id_fkey,
  ADD CONSTRAINT conversation_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES "user"(user_id) ON DELETE CASCADE;

ALTER TABLE password_reset_token
  DROP CONSTRAINT IF EXISTS password_reset_token_user_id_fkey,
  ADD CONSTRAINT password_reset_token_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES "user"(user_id) ON DELETE CASCADE;

ALTER TABLE user_feedback
  DROP CONSTRAINT IF EXISTS user_feedback_user_id_fkey,
  ADD CONSTRAINT user_feedback_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES "user"(user_id) ON DELETE CASCADE;

ALTER TABLE parent_invite
  DROP CONSTRAINT IF EXISTS parent_invite_user_id_fkey,
  ADD CONSTRAINT parent_invite_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES "user"(user_id) ON DELETE CASCADE;

ALTER TABLE quest
  DROP CONSTRAINT IF EXISTS quest_user_id_fkey,
  ADD CONSTRAINT quest_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES "user"(user_id) ON DELETE CASCADE;

ALTER TABLE student_skill_mastery
  DROP CONSTRAINT IF EXISTS student_skill_mastery_student_id_fkey,
  ADD CONSTRAINT student_skill_mastery_student_id_fkey
    FOREIGN KEY (student_id) REFERENCES "user"(user_id) ON DELETE CASCADE;

ALTER TABLE student_long_term_goal
  DROP CONSTRAINT IF EXISTS student_long_term_goal_user_id_fkey,
  ADD CONSTRAINT student_long_term_goal_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES "user"(user_id) ON DELETE CASCADE;

ALTER TABLE ltg_conversation
  DROP CONSTRAINT IF EXISTS ltg_conversation_user_id_fkey,
  ADD CONSTRAINT ltg_conversation_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES "user"(user_id) ON DELETE CASCADE;

ALTER TABLE enrollment
  DROP CONSTRAINT IF EXISTS enrollment_user_id_fkey,
  ADD CONSTRAINT enrollment_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES "user"(user_id) ON DELETE CASCADE;

-- period.owner_id → user: cascade so all period-child rows follow
ALTER TABLE period
  DROP CONSTRAINT IF EXISTS period_owner_id_fkey,
  ADD CONSTRAINT period_owner_id_fkey
    FOREIGN KEY (owner_id) REFERENCES "user"(user_id) ON DELETE CASCADE;

-- Preserve rows but null out the reference when the linked user is deleted
ALTER TABLE waitlist
  DROP CONSTRAINT IF EXISTS waitlist_user_id_fkey,
  ADD CONSTRAINT waitlist_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES "user"(user_id) ON DELETE SET NULL;

ALTER TABLE student
  DROP CONSTRAINT IF EXISTS student_created_by_parent_id_fkey,
  ADD CONSTRAINT student_created_by_parent_id_fkey
    FOREIGN KEY (created_by_parent_id) REFERENCES "user"(user_id) ON DELETE SET NULL;

-- ─── Cascades from period deletion ──────────────────────────────────────────

ALTER TABLE week
  DROP CONSTRAINT IF EXISTS week_period_id_fkey,
  ADD CONSTRAINT week_period_id_fkey
    FOREIGN KEY (period_id) REFERENCES period(period_id) ON DELETE CASCADE;

ALTER TABLE lesson
  DROP CONSTRAINT IF EXISTS lesson_period_id_fkey,
  ADD CONSTRAINT lesson_period_id_fkey
    FOREIGN KEY (period_id) REFERENCES period(period_id) ON DELETE CASCADE;

ALTER TABLE lesson_pptx
  DROP CONSTRAINT IF EXISTS lesson_pptx_period_id_fkey,
  ADD CONSTRAINT lesson_pptx_period_id_fkey
    FOREIGN KEY (period_id) REFERENCES period(period_id) ON DELETE CASCADE;

ALTER TABLE concept
  DROP CONSTRAINT IF EXISTS concept_period_id_fkey,
  ADD CONSTRAINT concept_period_id_fkey
    FOREIGN KEY (period_id) REFERENCES period(period_id) ON DELETE CASCADE;

ALTER TABLE skill
  DROP CONSTRAINT IF EXISTS skill_period_id_fkey,
  ADD CONSTRAINT skill_period_id_fkey
    FOREIGN KEY (period_id) REFERENCES period(period_id) ON DELETE CASCADE;

ALTER TABLE enrollment
  DROP CONSTRAINT IF EXISTS enrollment_period_id_fkey,
  ADD CONSTRAINT enrollment_period_id_fkey
    FOREIGN KEY (period_id) REFERENCES period(period_id) ON DELETE CASCADE;

ALTER TABLE quest
  DROP CONSTRAINT IF EXISTS quest_period_id_fkey,
  ADD CONSTRAINT quest_period_id_fkey
    FOREIGN KEY (period_id) REFERENCES period(period_id) ON DELETE CASCADE;

ALTER TABLE student_skill_mastery
  DROP CONSTRAINT IF EXISTS student_skill_mastery_period_id_fkey,
  ADD CONSTRAINT student_skill_mastery_period_id_fkey
    FOREIGN KEY (period_id) REFERENCES period(period_id) ON DELETE CASCADE;

ALTER TABLE student_long_term_goal
  DROP CONSTRAINT IF EXISTS student_long_term_goal_period_id_fkey,
  ADD CONSTRAINT student_long_term_goal_period_id_fkey
    FOREIGN KEY (period_id) REFERENCES period(period_id) ON DELETE CASCADE;

ALTER TABLE ltg_conversation
  DROP CONSTRAINT IF EXISTS ltg_conversation_period_id_fkey,
  ADD CONSTRAINT ltg_conversation_period_id_fkey
    FOREIGN KEY (period_id) REFERENCES period(period_id) ON DELETE CASCADE;

ALTER TABLE aggregated_metrics
  DROP CONSTRAINT IF EXISTS aggregated_metrics_period_id_fkey,
  ADD CONSTRAINT aggregated_metrics_period_id_fkey
    FOREIGN KEY (period_id) REFERENCES period(period_id) ON DELETE CASCADE;

ALTER TABLE marketplace_listing
  DROP CONSTRAINT IF EXISTS marketplace_listing_period_id_fkey,
  ADD CONSTRAINT marketplace_listing_period_id_fkey
    FOREIGN KEY (period_id) REFERENCES period(period_id) ON DELETE CASCADE;

-- ─── Helper function for parent link cleanup ────────────────────────────────
-- Removes a student_id from linked_student_ids for all parent rows that contain it.
-- Called by ParentDAO.remove_student_link during account deletion.

CREATE OR REPLACE FUNCTION array_remove_from_linked_students(target_student_id text)
RETURNS void
LANGUAGE sql
SECURITY DEFINER
AS $$
  UPDATE parent
  SET linked_student_ids = array_remove(linked_student_ids, target_student_id)
  WHERE target_student_id = ANY(linked_student_ids);
$$;
