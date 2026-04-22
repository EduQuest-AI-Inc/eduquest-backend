# TODO: Rename `linked_user_ids` → `linked_student_ids`

The `parent` table column `linked_user_ids` should be renamed to `linked_student_ids` for clarity — the stored values are specifically student `user_id`s, not arbitrary user IDs.

## Changes required

- `data_access/data_tables.md` — update column name in parent table
- `models/parent.py` — rename field on `Parent` model
- `data_access/supabase/parent_dao.py` — update column reference
- `routes/auth/routes.py` — update `.get('linked_user_ids')` and dict key in `update_parent` call
- `routes/parent/parent_service.py` — update `.get('linked_user_ids', [])`
- `routes/period/routes.py` — update `.get('linked_user_ids')` and dict key in `update_parent` call
- New Supabase migration: `ALTER TABLE parent RENAME COLUMN linked_user_ids TO linked_student_ids;`
