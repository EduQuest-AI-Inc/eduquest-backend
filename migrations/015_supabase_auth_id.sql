-- Migration 015: add supabase_auth_id to user table
-- Nullable initially — existing rows are backfilled lazily on login.
-- UNIQUE because a single Supabase Auth entry must not map to two EduQuest users.

ALTER TABLE "user"
  ADD COLUMN IF NOT EXISTS supabase_auth_id uuid UNIQUE;

-- Index for the Phase 3 lookup: given a JWT's auth.uid(), find the EduQuest user_id.
CREATE INDEX IF NOT EXISTS idx_user_supabase_auth_id
  ON "user"(supabase_auth_id);
