-- Migration 008: Quest step-by-step instructions
-- Run this migration in the Supabase SQL editor before deploying the corresponding code.

-- ============================================================
-- Task 1: Convert instructions column from text to jsonb
-- ============================================================
-- Existing text rows are wrapped as a single-step list so legacy data renders.
ALTER TABLE quest
    ALTER COLUMN instructions TYPE jsonb
    USING CASE
        WHEN instructions IS NULL OR instructions = ''
            THEN '[]'::jsonb
        ELSE jsonb_build_array(jsonb_build_object('step', 1, 'text', instructions))
    END;

-- ============================================================
-- Task 2: Add completed_steps column for per-student progress tracking
-- ============================================================
ALTER TABLE quest ADD COLUMN IF NOT EXISTS completed_steps jsonb DEFAULT '[]'::jsonb;
