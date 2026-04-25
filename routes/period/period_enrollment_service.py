import logging
from typing import Dict, Any, List
from exceptions.validation_error import ValidationError
from exceptions.not_found_error import NotFoundError
from data_access.period_dao import PeriodDAO
from data_access.student_dao import StudentDAO
from data_access.enrollment_dao import EnrollmentDAO
from data_access.quest_dao import QuestDAO
from data_access.ltg_conversation_dao import LtgConversationDAO
from data_access.conversation_dao import ConversationDAO

logger = logging.getLogger(__name__)

from models.enrollment import Enrollment

TUTORIAL_PERIOD_ID = "PRECALC-58F9-88F5"


class PeriodEnrollmentService:

    def __init__(self) -> None:
        self.period_dao = PeriodDAO()
        self.student_dao = StudentDAO()
        self.enrollment_dao = EnrollmentDAO()
        self.quest_dao = QuestDAO()
        self.ltg_conversation_dao = LtgConversationDAO()
        self.conversation_dao = ConversationDAO()

    def get_my_periods(self, user_id: str) -> List[Dict[str, Any]]:
        enrollments = self.enrollment_dao.get_enrollments_by_student(user_id)
        period_ids = [e['period_id'] for e in enrollments]

        ltg_rows = (
            self.student_dao.client
            .table('student_long_term_goal')
            .select('period_id, goal_text')
            .eq('user_id', user_id)
            .execute()
        )
        ltg_data: list[Dict[str, Any]] = ltg_rows.data or []
        ltg_map = {r['period_id']: r['goal_text'] for r in ltg_data}

        result = []
        for pid in period_ids:
            period = self.period_dao.get_period_by_id(pid)
            if not period:
                continue
            result.append({
                'period_id': pid,
                'course_name': period.get('name', pid),
                'long_term_goal': ltg_map.get(pid),
            })
        return result

    def verify_period_id(self, user_id: str, period_id: str) -> Any:
        if not period_id:
            raise ValidationError("Missing period ID")

        period = self.period_dao.get_period_by_id(period_id)
        if not period:
            raise NotFoundError("Invalid period ID")

        student = self.student_dao.get_student_by_id(user_id)
        if not student:
            raise Exception("Student not found")

        existing_enrollments = self.enrollment_dao.get_enrollments_by_student(user_id)
        enrolled_period_ids = [e['period_id'] for e in existing_enrollments]

        if period_id in enrolled_period_ids:
            raise ValidationError(f"You are already enrolled in period {period_id}")

        enrollment = Enrollment(period_id=period_id, user_id=user_id, semester="2024-spring")
        self.enrollment_dao.add_enrollment(enrollment)

        if period_id != TUTORIAL_PERIOD_ID:
            self._cleanup_tutorial_periods(user_id)

        return period

    def unenroll_from_period(self, user_id: str, period_id: str) -> Dict[str, Any]:
        if not period_id:
            raise ValidationError("Missing period ID")

        student = self.student_dao.get_student_by_id(user_id)
        if not student:
            raise Exception("Student not found")

        existing_enrollments = self.enrollment_dao.get_enrollments_by_student(user_id)
        enrolled_period_ids = [e['period_id'] for e in existing_enrollments]
        if period_id not in enrolled_period_ids:
            raise ValidationError(f"You are not enrolled in period {period_id}")

        try:
            self.enrollment_dao.delete_enrollment(user_id, period_id)
        except Exception as e:
            logger.warning("Could not delete enrollment row: %s", e)

        updated_enrollments = [p for p in enrolled_period_ids if p != period_id]

        conversation_id = self.ltg_conversation_dao.delete_conversation(user_id, period_id)
        if conversation_id:
            try:
                self.conversation_dao.delete_conversation(conversation_id)
            except Exception as e:
                logger.warning("Could not delete conversation %s: %s", conversation_id, e)

        period_obj = self.period_dao.get_period_by_id(period_id)
        period_name = period_obj.get('name', period_id) if period_obj else period_id
        long_term_goals = student.get('long_term_goal', {})
        if isinstance(long_term_goals, list):
            long_term_goals = {}
        goal_removed = False
        for key in (period_name, period_id):
            if key in long_term_goals:
                long_term_goals.pop(key)
                goal_removed = True
        if goal_removed:
            self.student_dao.update_student(user_id, {'long_term_goal': long_term_goals})

        quests = self.quest_dao.get_quests_by_student_and_period(user_id, period_id)
        for q in quests:
            self.quest_dao.delete_quest(q['quest_id'])

        return {
            "message": f"Successfully unenrolled from period {period_id}",
            "period_id": period_id,
            "remaining_enrollments": updated_enrollments,
        }

    def assert_enrolled(self, user_id: str, period_id: str) -> None:
        enrollments = self.enrollment_dao.get_enrollments_by_period(period_id)
        if not any(e['user_id'] == user_id for e in enrollments):
            raise Exception(f"Student {user_id} is not enrolled in period {period_id}")

    def _cleanup_tutorial_periods(self, user_id: str) -> None:
        existing_enrollments = self.enrollment_dao.get_enrollments_by_student(user_id)
        enrolled_period_ids = [e['period_id'] for e in existing_enrollments]
        if TUTORIAL_PERIOD_ID in enrolled_period_ids:
            try:
                self.enrollment_dao.delete_enrollment(user_id, TUTORIAL_PERIOD_ID)
            except Exception as e:
                logger.error("Error removing tutorial enrollment: %s", e)
