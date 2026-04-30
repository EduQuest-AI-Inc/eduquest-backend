"""
Thin orchestrator — delegates to focused sub-services.
Kept for backwards compatibility so routes.py imports remain unchanged.
"""
from services.enrollment.enrollment_service import EnrollmentService
from services.period.period_quest_service import PeriodQuestService
from services.conversation.ltg_service import run_initiate_ltg, run_continue_ltg


class PeriodService:

    def __init__(self) -> None:
        self._enrollment = EnrollmentService()
        self._quest = PeriodQuestService()
        self.period_dao = self._enrollment.period_dao

    def get_my_periods(self, user_id):
        return self._enrollment.get_my_periods(user_id)

    def verify_period_id(self, user_id, period_id, allow_parent_period: bool = False):
        return self._enrollment.verify_period_id(user_id, period_id, allow_parent_period)

    def unenroll_from_period(self, user_id, period_id):
        return self._enrollment.unenroll_from_period(user_id, period_id)

    def initiate_ltg_conversation(self, user_id, period_id):
        return run_initiate_ltg(user_id, period_id)

    def continue_ltg_conversation(self, user_id, conversation_type, conversation_id, message, period_id=None):
        return run_continue_ltg(user_id, conversation_type, conversation_id, message, period_id)

    def start_homework_agent(self, user_id, period_id):
        return self._quest.start_homework_agent(user_id, period_id)

    def get_parent_periods_for_student(self, student_id: str):
        return self._enrollment.get_parent_periods_for_student(student_id)

    def has_teacher_access_to_student(self, teacher_id: str, student_id: str) -> bool:
        return self._enrollment.has_teacher_access_to_student(teacher_id, student_id)

    def update_quests_with_recommended_change(self, caller_id: str, caller_role: str, period_id: str, recommended_change: str):
        return self._quest.update_quests_with_recommended_change(caller_id, caller_role, period_id, recommended_change)
