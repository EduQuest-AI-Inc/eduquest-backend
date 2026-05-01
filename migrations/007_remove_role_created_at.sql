-- Remove redundant created_at columns from role tables; user.created_at is authoritative
ALTER TABLE student DROP COLUMN IF EXISTS created_at;
ALTER TABLE teacher DROP COLUMN IF EXISTS created_at;
ALTER TABLE parent  DROP COLUMN IF EXISTS created_at;
