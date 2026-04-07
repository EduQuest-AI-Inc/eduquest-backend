from typing import Dict, Any, Optional, List

from data_access.supabase.base_dao import SupabaseBaseDAO


class SchoolDAO(SupabaseBaseDAO):
    def __init__(self):
        super().__init__('school')

    def add_school(self, school) -> None:
        self._insert({
            'school_id': school.school_id,
            'school_name': school.school_name,
        })

    def get_school_by_id(self, school_id: str) -> List[Dict[str, Any]]:
        # DynamoDB version returned Items list; keep the same return shape
        return self._select_eq('school_id', school_id)

    def update_school(self, school_id: str, updates: Dict[str, Any]) -> None:
        self._update({'school_id': school_id}, updates)

    def delete_school(self, school_id: str) -> None:
        self._delete({'school_id': school_id})
