-- Migration 002: User table normalization
--
-- Extract shared fields from student/teacher/parent into a new `user` table.
-- Role tables keep only role-specific fields. FKs cascade on delete.

-- 1. Create user table
CREATE TABLE "user" (
    user_id TEXT PRIMARY KEY,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    email TEXT NOT NULL,
    email_lc TEXT NOT NULL,
    password TEXT NOT NULL,
    last_login TEXT,
    role TEXT NOT NULL CHECK (role IN ('student', 'teacher', 'parent')),
    canvas_api_url TEXT,
    canvas_api_key TEXT
);
CREATE UNIQUE INDEX idx_user_email_lc ON "user" (email_lc);

-- 2. Populate from existing tables
INSERT INTO "user" (user_id, first_name, last_name, email, email_lc, password, last_login, role, canvas_api_url, canvas_api_key)
SELECT user_id, first_name, last_name, email, email_lc, password, last_login, 'student', canvas_api_url, canvas_api_key FROM student;

INSERT INTO "user" (user_id, first_name, last_name, email, email_lc, password, last_login, role)
SELECT user_id, first_name, last_name, email, email_lc, password, last_login, 'teacher' FROM teacher;

INSERT INTO "user" (user_id, first_name, last_name, email, email_lc, password, last_login, role)
SELECT user_id, first_name, last_name, email, email_lc, password, last_login, 'parent' FROM parent;

-- 3. Add FK constraints (CASCADE so deleting user cascades to role table)
ALTER TABLE student ADD CONSTRAINT fk_student_user FOREIGN KEY (user_id) REFERENCES "user"(user_id) ON DELETE CASCADE;
ALTER TABLE teacher ADD CONSTRAINT fk_teacher_user FOREIGN KEY (user_id) REFERENCES "user"(user_id) ON DELETE CASCADE;
ALTER TABLE parent  ADD CONSTRAINT fk_parent_user  FOREIGN KEY (user_id) REFERENCES "user"(user_id) ON DELETE CASCADE;

-- 4. Drop shared columns from role tables
ALTER TABLE student DROP COLUMN first_name,
                    DROP COLUMN last_name,
                    DROP COLUMN email,
                    DROP COLUMN email_lc,
                    DROP COLUMN password,
                    DROP COLUMN last_login,
                    DROP COLUMN canvas_api_url,
                    DROP COLUMN canvas_api_key;

ALTER TABLE teacher DROP COLUMN first_name,
                    DROP COLUMN last_name,
                    DROP COLUMN email,
                    DROP COLUMN email_lc,
                    DROP COLUMN password,
                    DROP COLUMN last_login;

ALTER TABLE parent  DROP COLUMN first_name,
                    DROP COLUMN last_name,
                    DROP COLUMN email,
                    DROP COLUMN email_lc,
                    DROP COLUMN password,
                    DROP COLUMN last_login;
