from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from data_access.supabase.base_dao import SupabaseBaseDAO
from models.quest import Quest


class QuestDAO(SupabaseBaseDAO):
    def __init__(self) -> None:
        super().__init__('quest')

    def add_quest(self, quest: Quest) -> None:
        self._insert({
            'quest_id': quest.quest_id,
            'user_id': quest.user_id,
            'period_id': quest.period_id,
            'week': quest.week,
            'description': quest.description,
            'instructions': quest.instructions,
            'rubric': quest.rubric,
            'skills': quest.skills,
            'due_date': quest.due_date,
            'status': quest.status,
            'grade': quest.grade,
            'feedback': quest.feedback,
        })

    def get_quest_by_id(self, quest_id: str) -> Optional[Dict[str, Any]]:
        return self._select_by_id('quest_id', quest_id)

    def get_quests_by_week(self, week: int) -> List[Dict[str, Any]]:
        return self._select_eq('week', week)

    def get_quests_by_status(self, status: str) -> List[Dict[str, Any]]:
        return self._select_eq('status', status)

    def update_quest(self, quest_id: str, updates: Dict[str, Any]) -> None:
        updates['last_updated_at'] = datetime.now(timezone.utc).isoformat()
        self._update({'quest_id': quest_id}, updates)

    def update_quest_grade_and_feedback(self, quest_id: str, grade: dict, feedback: str) -> None:
        self.update_quest(quest_id, {
            'grade': grade,
            'feedback': feedback,
            'status': 'completed',
        })

    def update_quest_status(self, quest_id: str, status: str) -> None:
        self.update_quest(quest_id, {'status': status})

    def delete_quest(self, quest_id: str) -> None:
        self._delete({'quest_id': quest_id})

    def get_all_quests(self) -> List[Dict[str, Any]]:
        response = self._table().select('*').execute()
        return self._rows(response.data)

    def get_quests_by_date_range(self, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        response = (
            self._table()
            .select('*')
            .gte('due_date', start_date)
            .lte('due_date', end_date)
            .execute()
        )
        return self._rows(response.data)

    def get_quests_by_skills(self, skills: str) -> List[Dict[str, Any]]:
        response = (
            self._table()
            .select('*')
            .ilike('skills', f'%{skills}%')
            .execute()
        )
        return self._rows(response.data)

    def get_quests_by_student(self, user_id: str) -> List[Dict[str, Any]]:
        return self._select_eq('user_id', user_id)

    def get_quests_by_student_and_period(self, user_id: str, period_id: str) -> List[Dict[str, Any]]:
        response = (
            self._table()
            .select('*')
            .eq('user_id', user_id)
            .eq('period_id', period_id)
            .execute()
        )
        return self._rows(response.data)
