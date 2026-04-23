-- Migration 004: Schema refactor
-- Run this migration against Supabase before deploying the corresponding code changes.
-- Order matters: later tasks depend on earlier ones completing successfully.

-- ============================================================
-- Task 1: Remove email_lc from user table
-- ============================================================
ALTER TABLE "user" DROP COLUMN IF EXISTS email_lc;
DROP INDEX IF EXISTS idx_user_email_lc;
CREATE UNIQUE INDEX IF NOT EXISTS idx_user_email ON "user"(email);

-- ============================================================
-- Task 2: Remove email_lc from password_reset_token table
-- ============================================================
ALTER TABLE password_reset_token RENAME COLUMN email_lc TO email;

-- ============================================================
-- Task 3: Rename linked_user_ids -> linked_student_ids in parent table
-- ============================================================
ALTER TABLE parent RENAME COLUMN linked_user_ids TO linked_student_ids;

-- ============================================================
-- Task 4: Add missing indexes
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_enrollment_user_id ON enrollment(user_id);
CREATE INDEX IF NOT EXISTS idx_conversation_user_id ON conversation(user_id);
CREATE INDEX IF NOT EXISTS idx_period_owner_id ON period(owner_id);

-- ============================================================
-- Task 5: Rename individual_quest -> quest, drop weekly_quest
-- ============================================================
-- Rename table
ALTER TABLE individual_quest RENAME TO quest;

-- Rename PK column
ALTER TABLE quest RENAME COLUMN individual_quest_id TO quest_id;

-- Drop the old quest_id FK column (was a FK to weekly_quest)
-- This column pointed to weekly_quest.quest_id and is being replaced
-- by a direct (user_id, period_id) query pattern.
ALTER TABLE quest DROP COLUMN IF EXISTS quest_id_weekly;

-- Add index on (user_id, period_id) for fast per-student-per-period queries
CREATE INDEX IF NOT EXISTS idx_quest_user_period ON quest(user_id, period_id);

-- Drop weekly_quest table entirely
DROP TABLE IF EXISTS weekly_quest;

-- ============================================================
-- Task 6: Clean up conversation table
-- ============================================================
-- Drop role column (derivable from user.role via user_id)
ALTER TABLE conversation DROP COLUMN IF EXISTS role;

-- ============================================================
-- Task 7: Drop role from password_reset_token table
-- ============================================================
ALTER TABLE password_reset_token DROP COLUMN IF EXISTS role;

-- ============================================================
-- Task 8: Replace school table with school_name string
-- ============================================================
-- Add school_name string columns
ALTER TABLE student ADD COLUMN IF NOT EXISTS school_name TEXT;
ALTER TABLE teacher ADD COLUMN IF NOT EXISTS school_name TEXT;

-- Drop school_id FK columns (after migrating data if needed)
-- NOTE: if you have existing school_name data in the school table,
-- run this first to migrate it:
--   UPDATE student s SET school_name = sc.school_name
--     FROM school sc WHERE s.school_id = sc.school_id;
--   UPDATE teacher t SET school_name = sc.school_name
--     FROM school sc WHERE t.school_id = sc.school_id;
ALTER TABLE student DROP COLUMN IF EXISTS school_id;
ALTER TABLE teacher DROP COLUMN IF EXISTS school_id;

-- Drop school table
DROP TABLE IF EXISTS school;

-- ============================================================
-- Task 9: Merge pilot_waitlist and parent_waitlist into waitlist
-- ============================================================
-- Create the unified waitlist table
CREATE TABLE IF NOT EXISTS waitlist (
    waitlist_id  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      TEXT UNIQUE REFERENCES "user"(user_id) ON DELETE CASCADE,
    email        TEXT UNIQUE NOT NULL,
    joined_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    position     INTEGER NOT NULL DEFAULT 0,
    referral_code TEXT UNIQUE,
    referred_by  TEXT REFERENCES "user"(user_id),
    status       TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved'))
);

-- Migrate existing pilot_waitlist data
-- (teacher_id maps to user_id; other columns map directly)
INSERT INTO waitlist (user_id, email, joined_at, position, referral_code, referred_by, status)
SELECT
    teacher_id,
    email,
    COALESCE(joined_at::TIMESTAMPTZ, now()),
    COALESCE(position, 0),
    referral_code,
    referred_by,
    COALESCE(status, 'pending')
FROM pilot_waitlist
ON CONFLICT (email) DO NOTHING;

-- Drop old tables
DROP TABLE IF EXISTS pilot_waitlist;
DROP TABLE IF EXISTS parent_waitlist;

-- ============================================================
-- Task 10: Fix enrollment key structure
-- ============================================================
-- Add surrogate PK if it doesn't exist
ALTER TABLE enrollment ADD COLUMN IF NOT EXISTS enrollment_id UUID DEFAULT gen_random_uuid();

-- Make enrollment_id the primary key (drop old PK first if needed)
-- NOTE: In Supabase, a table may already have a hidden id PK. Check first.
-- If the table has no PK, add one:
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE table_name = 'enrollment' AND constraint_type = 'PRIMARY KEY'
    ) THEN
        ALTER TABLE enrollment ADD PRIMARY KEY (enrollment_id);
    END IF;
END
$$;

-- Add unique constraint on (user_id, period_id) to prevent duplicates
ALTER TABLE enrollment DROP CONSTRAINT IF EXISTS enrollment_user_period_unique;
ALTER TABLE enrollment ADD CONSTRAINT enrollment_user_period_unique UNIQUE (user_id, period_id);

-- ============================================================
-- Task 11: Store quest.grade as JSONB instead of a JSON string
-- ============================================================
-- Convert grade column from text to jsonb.
-- Existing string grades are wrapped in a JSON object for compatibility.
ALTER TABLE quest
    ALTER COLUMN grade TYPE JSONB
    USING CASE
        WHEN grade IS NULL THEN NULL
        WHEN grade ~ '^\\{' THEN grade::JSONB
        ELSE jsonb_build_object('overall_score', grade, 'detailed_grade', NULL)
    END;

-- ============================================================
-- Task 12 (non-blocking): TTL cleanup via pg_cron
-- Complete steps 1-11 first; set this up after schema is stable.
-- ============================================================
-- Run these in the Supabase SQL editor AFTER enabling the pg_cron extension
-- in Supabase Dashboard > Database > Extensions.

-- SELECT cron.schedule(
--     'delete-expired-sessions',
--     '0 * * * *',  -- every hour
--     $$DELETE FROM session WHERE expires_at < now()$$
-- );

-- SELECT cron.schedule(
--     'delete-expired-password-reset-tokens',
--     '0 * * * *',
--     $$DELETE FROM password_reset_token WHERE expires_at < now()$$
-- );

-- SELECT cron.schedule(
--     'delete-expired-rate-limits',
--     '0 2 * * *',  -- daily at 2am
--     $$DELETE FROM password_reset_rate_limit WHERE window_start < now() - interval '24 hours'$$
-- );

-- ============================================================
-- Explicitly excluded from RLS (non-sensitive / internal tables)
-- ============================================================
-- waitlist       — public signup; no per-user scoping needed
-- password_reset_token      — Flask service role only
-- password_reset_rate_limit — Flask service role only
-- aggregated_metrics        — Flask service role only
