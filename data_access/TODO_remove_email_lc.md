# TODO: Remove `email_lc` Column

## Decision
Drop `email_lc` from the `user` table and use `email` exclusively for both display and lookups.

## Why It's Safe
`normalize_email()` in `utils/validation_utils.py` already strips and lowercases every email on write:

```python
def normalize_email(email):
    return email.strip().lower() if email else ''
```

So `email` is always lowercase — `email_lc` is a redundant duplicate that adds sync burden with no benefit.

## What To Do

1. **Supabase**: Drop the `email_lc` column from the `user` table.
2. **DAOs**: Find all references to `email_lc` in `data_access/supabase/` and replace with `email`.
3. **Routes/services**: Search the whole backend for `email_lc` and remove any remaining references.
4. **Verify**: Confirm `normalize_email()` is called before every insert/update that touches the email field.
