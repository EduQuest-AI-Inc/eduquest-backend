-- Migration 005: Move canvas credentials from user table to teacher table
--
-- canvas_api_url and canvas_api_key were added to user for a student Canvas
-- flow that was later removed. They are inert for all roles. Teachers now own
-- their Canvas credentials, so the columns belong on the teacher table.

-- Add to teacher table
ALTER TABLE teacher
    ADD COLUMN IF NOT EXISTS canvas_api_url TEXT,
    ADD COLUMN IF NOT EXISTS canvas_api_key TEXT;

-- Remove from user table
ALTER TABLE "user"
    DROP COLUMN IF EXISTS canvas_api_url,
    DROP COLUMN IF EXISTS canvas_api_key;
