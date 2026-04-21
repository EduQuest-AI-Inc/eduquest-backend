# User Table Normalization — Work Reference

Normalize `student`, `teacher`, `parent` tables by extracting shared fields into a new `user` table. Role tables keep only role-specific fields. Many callers can hit `UserDAO` directly without touching the role table.

---

## New Table Schemas

### `user` (new)
| Field | Type | Notes |
|---|---|---|
| `user_id` | string | PK |
| `first_name` | string | |
| `last_name` | string | |
| `email` | string | |
| `email_lc` | string | Unique index — canonical lowercase for lookups |
| `password` | string | Hashed |
| `last_login` | string | ISO timestamp |
| `role` | string | `"student"` \| `"teacher"` \| `"parent"` |
| `canvas_api_url` | string | Optional |
| `canvas_api_key` | string | Optional |

### `student` (trimmed — remove shared fields)
| Field | Type | Notes |
|---|---|---|
| `user_id` | string | PK + FK → `user.user_id` |
| `grade` | integer | |
| `strength` | list | |
| `weakness` | list | |
| `interest` | list | |
| `learning_style` | list | |
| `completed_tutorial` | boolean | Default: false |
| `school_id` | string | Optional |

### `teacher` (trimmed)
| Field | Type | Notes |
|---|---|---|
| `user_id` | string | PK + FK → `user.user_id` |
| `pilot_approved` | boolean | Default: false |
| `school_id` | string | Optional |

### `parent` (trimmed)
| Field | Type | Notes |
|---|---|---|
| `user_id` | string | PK + FK → `user.user_id` |
| `linked_user_ids` | list\<string\> | Default: [] |
| `vpc_verified_at` | string | Optional — COPPA 2025 compliance timestamp, set on invite accept |

---

## Migration

**File to create:** `migrations/002_user_table_normalization.sql`

```sql
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

-- 3. Add FK constraints
ALTER TABLE student ADD CONSTRAINT fk_student_user FOREIGN KEY (user_id) REFERENCES "user"(user_id) ON DELETE CASCADE;
ALTER TABLE teacher ADD CONSTRAINT fk_teacher_user FOREIGN KEY (user_id) REFERENCES "user"(user_id) ON DELETE CASCADE;
ALTER TABLE parent  ADD CONSTRAINT fk_parent_user  FOREIGN KEY (user_id) REFERENCES "user"(user_id) ON DELETE CASCADE;

-- 4. Drop shared columns from role tables
ALTER TABLE student DROP COLUMN first_name, DROP COLUMN last_name, DROP COLUMN email,
                    DROP COLUMN email_lc, DROP COLUMN password, DROP COLUMN last_login,
                    DROP COLUMN canvas_api_url, DROP COLUMN canvas_api_key;
ALTER TABLE teacher DROP COLUMN first_name, DROP COLUMN last_name, DROP COLUMN email,
                    DROP COLUMN email_lc, DROP COLUMN password, DROP COLUMN last_login;
ALTER TABLE parent  DROP COLUMN first_name, DROP COLUMN last_name, DROP COLUMN email,
                    DROP COLUMN email_lc, DROP COLUMN password, DROP COLUMN last_login;
```

---

## DAOs to Create / Modify

### New: `data_access/supabase/user_dao.py`
Methods:
- `get_by_id(user_id) -> dict | None`
- `get_by_email_lc(email_lc) -> dict | None`
- `update(user_id, updates: dict) -> dict`
- `delete(user_id)` — cascades to role table via FK

### `data_access/supabase/student_dao.py`
- `add_student`: insert `user` first, then `student`; compensating delete on role insert failure
- `get_student_by_id`: `SELECT user.*, student.* FROM student JOIN user USING (user_id)` → flat dict
- `get_student_by_email_lc`: `UserDAO.get_by_email_lc` + join `student`
- `update_student`: partition dict using `SHARED_USER_FIELDS`; shared → `UserDAO.update`, rest → `student` update
- `delete_student`: delete `student`, then `user` (or rely on CASCADE)
- `update_canvas_credentials` / `clear_canvas_credentials` → delegate to `UserDAO.update`

```python
SHARED_USER_FIELDS = {"first_name", "last_name", "email", "email_lc", "password", "last_login", "canvas_api_url", "canvas_api_key"}
```

### `data_access/supabase/teacher_dao.py`
- `add_teacher`: insert `user`, then `teacher`
- `get_teacher_by_id`: JOIN `user` + `teacher` → flat dict
- `get_teacher_by_email_lc`: **remove** — callers use `UserDAO.get_by_email_lc`
- `update_teacher`: role fields only → `teacher` table; password callers updated to use `UserDAO.update`
- `delete_teacher`: CASCADE handles it; just delete from `user`

### `data_access/supabase/parent_dao.py`
- `add_parent`: insert `user`, then `parent`
- `get_parent_by_id`: JOIN `user` + `parent` → flat dict
- `get_parent_by_email_lc`: **remove** — callers use `UserDAO.get_by_email_lc`
- `update_parent`: role fields only → `parent` table
- `delete_parent`: CASCADE handles it; just delete from `user`

---

## Call Sites to Update

| File | Current call | Replace with |
|---|---|---|
| `routes/auth/routes.py` | `get_student_by_email_lc` (signup check) | `UserDAO.get_by_email_lc` |
| `routes/auth/routes.py` | `get_teacher_by_email_lc` (signup check) | `UserDAO.get_by_email_lc` |
| `routes/auth/routes.py` | `get_parent_by_email_lc` (signup check) | `UserDAO.get_by_email_lc` |
| `routes/auth/password_reset_service.py` | `get_X_by_email_lc` | `UserDAO.get_by_email_lc` |
| `routes/auth/password_reset_service.py` | `update_X({"password": ...})` | `UserDAO.update` |
| `routes/conversation/conversation_service.py` | `get_teacher_by_id` (shared fields only) | `UserDAO.get_by_id` |

---

## Models to Update

- `models/student.py`, `models/teacher.py`, `models/parent.py` — remove shared fields
- Add a base `User` dataclass with shared fields; role models extend or reference it
- `auth_service.py` constructs these models — update field usage there too

---

## Verification

```bash
cd eduquest-backend && pytest
```

Manual checks:
- Student signup → profile fields readable
- Teacher signup → `pilot_approved` readable
- Parent signup → `linked_user_ids` readable
- Password reset → `user.password` updated
- Canvas creds update → `user.canvas_api_url/key` updated
- Supabase dashboard: `user` table populated, role tables have no shared columns
