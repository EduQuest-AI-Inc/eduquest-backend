from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from data_access.supabase.base_dao import SupabaseBaseDAO
from models.individual_quest import IndividualQuest


class IndividualQuestDAO(SupabaseBaseDAO):
    def __init__(self) -> None:
        super().__init__('individual_quest')

    def add_individual_quest(self, quest: IndividualQuest) -> None:
        self._insert({
            'individual_quest_id': quest.individual_quest_id,
            'quest_id': quest.quest_id,
            'user_id': quest.user_id,
            'period_id': quest.period_id,
            'week': quest.week,
            'description': getattr(quest, 'description', ''),
            'instructions': getattr(quest, 'instructions', ''),
            'rubric': getattr(quest, 'rubric', {}),
            'skills': getattr(quest, 'skills', ''),
            'due_date': getattr(quest, 'due_date', None),
            'status': getattr(quest, 'status', 'not_started'),
            'grade': getattr(quest, 'grade', None),
            'feedback': getattr(quest, 'feedback', None),
        })

    def get_individual_quest_by_id(self, individual_quest_id: str) -> Optional[Dict[str, Any]]:
        return self._select_by_id('individual_quest_id', individual_quest_id)

    def get_quests_by_week(self, week: int) -> List[Dict[str, Any]]:
        return self._select_eq('week', week)

    def get_quests_by_status(self, status: str) -> List[Dict[str, Any]]:
        return self._select_eq('status', status)

    def update_individual_quest(self, individual_quest_id: str, updates: Dict[str, Any]) -> None:
        updates['last_updated_at'] = datetime.now(timezone.utc).isoformat()
        self._update({'individual_quest_id': individual_quest_id}, updates)

    def update_quest_grade_and_feedback(self, individual_quest_id: str, grade: str, feedback: str) -> None:
        self.update_individual_quest(individual_quest_id, {
            'grade': grade,
            'feedback': feedback,
            'status': 'completed',
        })

    def update_quest_status(self, individual_quest_id: str, status: str) -> None:
        self.update_individual_quest(individual_quest_id, {'status': status})

    def delete_individual_quest(self, individual_quest_id: str) -> None:
        self._delete({'individual_quest_id': individual_quest_id})

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

    def get_quests_by_quest_id(self, quest_id: str) -> List[Dict[str, Any]]:
        return self._select_eq('quest_id', quest_id)

    def get_quests_by_student_and_period(self, user_id: str, period_id: str) -> List[Dict[str, Any]]:
        response = (
            self._table()
            .select('*')
            .eq('user_id', user_id)
            .eq('period_id', period_id)
            .execute()
        )
        return self._rows(response.data)
