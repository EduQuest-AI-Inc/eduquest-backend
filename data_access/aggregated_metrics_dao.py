from typing import Any

from data_access.base_dao import SupabaseBaseDAO


class AggregatedMetricsDAO(SupabaseBaseDAO):
    def __init__(self, jwt: str | None = None):
        super().__init__('aggregated_metrics', jwt=jwt)

    def get_by_period_id(self, period_id: str) -> list[dict[str, Any]]:
        response = self._execute(
            self._table()
            .select('week, skill_name, percentage, updated_at')
            .eq('period_id', period_id)
            .order('week', desc=False)
            .order('skill_name', desc=False)
        )
        return self._rows(response.data)
