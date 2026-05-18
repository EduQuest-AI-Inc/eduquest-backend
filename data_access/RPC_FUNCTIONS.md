# Supabase RPC Functions

Stored procedures called via PostgREST `rpc/`. All are invoked from the backend via `SupabaseBaseDAO._rpc()` — never called directly by the client.

---

## `fork_marketplace_listing`

> Atomically clones a published period and its full curriculum into a new period owned by a different user. Increments `fork_count` on the listing.

| Parameter         | Type | Description                                   |
| ----------------- | ---- | --------------------------------------------- |
| `p_listing_id`    | UUID | The listing to fork                           |
| `p_new_owner_id`  | TEXT | `user_id` of the user performing the fork     |
| `p_new_period_id` | TEXT | Pre-generated period ID for the cloned period |

Copies the full curriculum hierarchy: `period` → `week` → `lesson` → `concept` → `skill` → `concept_skill`. The cloned period shares `vector_store_id` and file references with the original rather than duplicating them.

Raises `listing_not_found` if the listing does not exist or is unpublished.

**Called by:** `MarketplaceListingDAO.fork()` in [marketplace_listing_dao.py](marketplace_listing_dao.py)

> If columns are added to or removed from `skill`, this function must be updated to match — the column list is explicit, not `SELECT *`.
