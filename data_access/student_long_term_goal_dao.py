from typing import Optional

from data_access.base_dao import SupabaseBaseDAO
from models.student_long_term_goal import StudentLongTermGoal


class StudentLongTermGoalDAO(SupabaseBaseDAO):
    def __init__(self) -> None:
        super().__init__('student_long_term_goal')

    def upsert(self, user_id: str, period_id: str, goal_text: str) -> None:
        goal = StudentLongTermGoal(user_id=user_id, period_id=period_id, goal_text=goal_text)
        self._upsert(goal.to_item())

    def get_by_student(self, user_id: str) -> dict[str, Optional[str]]:
        """Return {period_id: goal_text} for all of a student's goals."""
        rows = self._select_eq('user_id', user_id)
        return {r['period_id']: r['goal_text'] for r in rows}

    def get_by_student_and_period(self, user_id: str, period_id: str) -> Optional[str]:
        response = self._execute(
            self._table()
            .select('goal_text')
            .eq('user_id', user_id)
            .eq('period_id', period_id)
            .maybe_single()
        )
        row = self._row(response)
        return row['goal_text'] if row else None

    def delete(self, user_id: str, period_id: str) -> None:
        self._delete({'user_id': user_id, 'period_id': period_id})
