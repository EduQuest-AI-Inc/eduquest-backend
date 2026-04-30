# CLAUDE.md — Data Access

All DAOs live in `data_access/` and extend `SupabaseBaseDAO` from `base_dao.py`.

## DAO Pattern

```python
from data_access.base_dao import SupabaseBaseDAO

class ExampleDAO(SupabaseBaseDAO):
    def __init__(self):
        super().__init__('table_name')
```

One file per Supabase table.

## Normalized User Tables

Shared identity fields live in the `user` table:

- `first_name`, `last_name`, `email` (UNIQUE constraint), `password`, `last_login`, `canvas_api_url`, `canvas_api_key`

Role tables (`student`, `teacher`, `parent`) hold only role-specific fields and a FK to `user.user_id` with `ON DELETE CASCADE`.

## DAOs

**UserDAO** (`user_dao.py`):

- `get_by_id`, `get_by_email`, `update`, `delete`
- All email uniqueness checks and password resets go through `UserDAO` directly — no need to query all three role tables

**Role DAOs** (`student_dao.py`, `teacher_dao.py`, `parent_dao.py`):

- Each embeds a `UserDAO`
- `add_*` inserts into both `user` and role tables atomically
- `get_*_by_id` JOINs via `_join_user()` and returns a flat dict
- `SHARED_USER_FIELDS` constant drives update partitioning: shared fields route to `UserDAO.update`, role-specific fields go to the role table

