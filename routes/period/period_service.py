"""
Thin orchestrator — delegates to focused sub-services.
Kept for backwards compatibility so routes.py imports remain unchanged.
"""
from routes.period.period_enrollment_service import PeriodEnrollmentService
from routes.period.period_ltg_service import PeriodLTGService
from routes.period.period_quest_service import PeriodQuestService
from data_access.supabase.session_dao import SessionDAO
from data_access.supabase.period_dao import PeriodDAO


class PeriodService:

    def __init__(self):
        self._enrollment = PeriodEnrollmentService()
        self._ltg = PeriodLTGService()
        self._quest = PeriodQuestService()
        # Expose DAOs directly so routes.py can access them (legacy usage)
        self.session_dao = self._enrollment.session_dao
        self.period_dao = self._enrollment.period_dao

    def get_my_periods(self, auth_token):
        return self._enrollment.get_my_periods(auth_token)

    def verify_period_id(self, auth_token, period_id):
        return self._enrollment.verify_period_id(auth_token, period_id)

    def unenroll_from_period(self, auth_token, period_id):
        return self._enrollment.unenroll_from_period(auth_token, period_id)

    def initiate_ltg_conversation(self, auth_token, period_id):
        return self._ltg.initiate_ltg_conversation(auth_token, period_id)

    def continue_ltg_conversation(self, auth_token, conversation_type, conversation_id, message, period_id=None):
        return self._ltg.continue_ltg_conversation(auth_token, conversation_type, conversation_id, message, period_id)

    def start_homework_agent(self, auth_token, user_id, period_id):
        return self._quest.start_homework_agent(auth_token, user_id, period_id)

    def update_quests_with_recommended_change(self, auth_token, period_id, recommended_change, user_id=None):
        return self._quest.update_quests_with_recommended_change(auth_token, user_id, period_id, recommended_change)
