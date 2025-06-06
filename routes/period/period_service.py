from typing import Dict, Any
from data_access.period_dao import PeriodDAO

class PeriodService:

    def __init__(self):
        self.period_dao = PeriodDAO()

    def verify_period_id(self, period_id: str) -> Any:
        if not period_id:
            raise ValueError("Missing period ID")

        period_items = self.period_dao.get_period_by_id(period_id)

        if not period_items:
            raise LookupError("Invalid period ID")

        return period_items[0]