from data_access.supabase.config import get_supabase_client
from supabase import Client


class SupabaseBaseDAO:
    """Base class for all Supabase DAOs.

    Provides thin wrappers around the PostgREST query builder so that
    concrete DAOs stay concise.
    """

    def __init__(self, table_name: str) -> None:
        self.client: Client = get_supabase_client()
        self.table_name = table_name

    # -- helpers ---------------------------------------------------------------

    def _table(self):
        return self.client.table(self.table_name)

    def _insert(self, data: dict) -> dict:
        response = self._table().insert(data).execute()
        return response.data[0] if response.data else {}

    def _upsert(self, data: dict) -> dict:
        response = self._table().upsert(data).execute()
        return response.data[0] if response.data else {}

    def _select_by_id(self, id_column: str, id_value) -> dict | None:
        response = (
            self._table()
            .select('*')
            .eq(id_column, id_value)
            .maybe_single()
            .execute()
        )
        return response.data if response is not None else None

    def _select_eq(self, column: str, value) -> list[dict]:
        response = (
            self._table()
            .select('*')
            .eq(column, value)
            .execute()
        )
        return response.data or []

    def _update(self, filters: dict, updates: dict) -> list[dict]:
        query = self._table().update(updates)
        for col, val in filters.items():
            query = query.eq(col, val)
        response = query.execute()
        return response.data or []

    def _delete(self, filters: dict) -> list[dict]:
        query = self._table().delete()
        for col, val in filters.items():
            query = query.eq(col, val)
        response = query.execute()
        return response.data or []

    def _rpc(self, function_name: str, params: dict) -> dict | list:
        response = self.client.rpc(function_name, params).execute()
        return response.data
