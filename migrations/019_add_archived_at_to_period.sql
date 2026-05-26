-- Migration 019: Add archived_at column to the period table.
-- NULL = active; a non-null timestamp means the class has been soft-deleted
-- (archived) by its owner. The row is preserved; enrollment-based access
-- for already-enrolled students is unaffected.
ALTER TABLE period
  ADD COLUMN IF NOT EXISTS archived_at TIMESTAMPTZ NULL;
