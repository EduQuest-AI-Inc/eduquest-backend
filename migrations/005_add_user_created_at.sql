-- Migration 005: Add created_at to user table
-- Run this migration against Supabase before deploying the corresponding code changes.

ALTER TABLE "user"
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT now();
