"""
Thin orchestrator — delegates to focused sub-services.
Kept for backwards compatibility so routes.py imports remain unchanged.
"""
from routes.period.period_enrollment_service import PeriodEnrollmentService
from routes.period.period_ltg_service import PeriodLTGService
from routes.period.period_quest_service import PeriodQuestService


class PeriodService:

    def __init__(self) -> None:
        self._enrollment = PeriodEnrollmentService()
        self._ltg = PeriodLTGService()
        self._quest = PeriodQuestService()
        self.period_dao = self._enrollment.period_dao

    def get_my_periods(self, user_id):
        return self._enrollment.get_my_periods(user_id)

    def verify_period_id(self, user_id, period_id):
        return self._enrollment.verify_period_id(user_id, period_id)

    def unenroll_from_period(self, user_id, period_id):
        return self._enrollment.unenroll_from_period(user_id, period_id)

    def initiate_ltg_conversation(self, user_id, period_id):
        return self._ltg.initiate_ltg_conversation(user_id, period_id)

    def continue_ltg_conversation(self, user_id, conversation_type, conversation_id, message, period_id=None):
        return self._ltg.continue_ltg_conversation(user_id, conversation_type, conversation_id, message, period_id)

    def start_homework_agent(self, user_id, period_id):
        return self._quest.start_homework_agent(user_id, period_id)

    def update_quests_with_recommended_change(self, auth_token, period_id, recommended_change, user_id=None):
        return self._quest.update_quests_with_recommended_change(auth_token, user_id, period_id, recommended_change)
