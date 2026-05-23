from typing import Any

from data_access.base_dao import SupabaseBaseDAO
from models.week import Week


class WeekDAO(SupabaseBaseDAO):
    def __init__(self, jwt: str | None = None) -> None:
        super().__init__('week', jwt=jwt)

    def insert_week(self, week: Week) -> None:
        self._insert(week.to_item())

    def get_weeks_by_period(self, period_id: str) -> list[dict[str, Any]]:
        return self._select_eq('period_id', period_id)

    def delete_weeks_by_period(self, period_id: str) -> None:
        self._delete({'period_id': period_id})
