from typing import Any, cast

from data_access.config import get_supabase_client
from exceptions.validation_error import ValidationError
from postgrest import APIError as PostgrestAPIError
from postgrest._sync.request_builder import SyncRequestBuilder
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

    def _table(self) -> SyncRequestBuilder:
        return self.client.table(self.table_name)

    def _execute(self, query: Any) -> Any:
        try:
            return query.execute()
        except PostgrestAPIError as e:
            raise ValidationError(str(e)) from e

    def _insert(self, data: dict[str, Any]) -> dict[str, Any]:
        response = self._execute(self._table().insert(data))
        return cast(dict[str, Any], response.data[0]) if response.data else {}

    def _upsert(self, data: dict[str, Any]) -> dict[str, Any]:
        response = self._execute(self._table().upsert(data))
        return cast(dict[str, Any], response.data[0]) if response.data else {}

    def _select_by_id(self, id_column: str, id_value: str) -> dict[str, Any] | None:
        response = self._execute(
            self._table()
            .select('*')
            .eq(id_column, id_value)
            .maybe_single()
        )
        return cast(dict[str, Any], response.data) if response.data is not None else None

    def _select_eq(self, column: str, value: str) -> list[dict[str, Any]]:
        response = self._execute(
            self._table()
            .select('*')
            .eq(column, value)
        )
        return cast(list[dict[str, Any]], response.data) if response.data else []

    def _update(self, filters: dict[str, Any], updates: dict[str, Any]) -> list[dict[str, Any]]:
        query = self._table().update(updates)
        for col, val in filters.items():
            query = query.eq(col, val)
        response = self._execute(query)
        return cast(list[dict[str, Any]], response.data) if response.data else []

    def _delete(self, filters: dict[str, Any]) -> list[dict[str, Any]]:
        query = self._table().delete()
        for col, val in filters.items():
            query = query.eq(col, val)
        response = self._execute(query)
        return cast(list[dict[str, Any]], response.data) if response.data else []

    def _rows(self, data: Any) -> list[dict[str, Any]]:
        return cast(list[dict[str, Any]], data) if data else []

    def _row(self, response: Any) -> dict[str, Any] | None:
        data = response.data if hasattr(response, 'data') else response
        return cast(dict[str, Any], data) if data is not None else None

    def _rpc(self, function_name: str, params: dict[str, Any]) -> dict[str, Any] | list[Any]:
        response = self._execute(self.client.rpc(function_name, params))
        return cast(dict[str, Any] | list[Any], response.data)

    def _join_user(self, id_column: str, id_value: str) -> dict[str, Any] | None:
        """JOIN this role table with user and return a flat dict."""
        response = self._execute(
            self.client.table(self.table_name)
            .select('*, user!inner(*)')
            .eq(id_column, id_value)
            .maybe_single()
        )
        data = self._row(response)
        if not data:
            return None
        data = dict(data)
        user_data = data.pop('user', {})
        data.update(user_data)
        return data
