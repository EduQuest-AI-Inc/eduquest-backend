from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from data_access.supabase.base_dao import SupabaseBaseDAO


class WeeklyQuestDAO(SupabaseBaseDAO):
    def __init__(self):
        super().__init__('weekly_quest')

    def add_weekly_quest(self, quest) -> None:
        self._insert({
            'quest_id': quest.quest_id,
            'student_id': quest.student_id,
            'period_id': quest.period_id,
            'week': quest.week,
            'year': getattr(quest, 'year', None),
            'status': getattr(quest, 'status', 'pending'),
        })

    def get_weekly_quest_by_id(self, quest_id: str) -> Optional[Dict[str, Any]]:
        return self._select_by_id('quest_id', quest_id)

    def update_weekly_quest(self, quest_id: str, updates: Dict[str, Any]) -> None:
        updates['last_updated_at'] = datetime.now(timezone.utc).isoformat()
        self._update({'quest_id': quest_id}, updates)

    def delete_weekly_quest(self, quest_id: str) -> None:
        self._delete({'quest_id': quest_id})

    def get_quests_by_student_and_period(self, student_id: str, period_id: str) -> List[Dict[str, Any]]:
        response = (
            self._table()
            .select('*')
            .eq('student_id', student_id)
            .eq('period_id', period_id)
            .execute()
        )
        return response.data or []

    def get_weekly_quest_by_student_and_period(self, student_id: str, period_id: str) -> Optional[Dict[str, Any]]:
        """Get the weekly quest for a student in a specific period (returns first match)."""
        results = self.get_quests_by_student_and_period(student_id, period_id)
        return results[0] if results else None
