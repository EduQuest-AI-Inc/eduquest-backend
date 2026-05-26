import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from data_access.conversation_dao import ConversationDAO
from data_access.enrollment_dao import EnrollmentDAO
from data_access.ltg_conversation_dao import LtgConversationDAO
from data_access.parent_dao import ParentDAO
from data_access.period_dao import PeriodDAO
from data_access.quest_dao import QuestDAO
from data_access.student_dao import StudentDAO
from data_access.student_long_term_goal_dao import StudentLongTermGoalDAO
from data_access.user_dao import UserDAO
from exceptions.not_found_error import NotFoundError
from exceptions.validation_error import ValidationError
from models.enrollment import Enrollment

logger = logging.getLogger(__name__)

TUTORIAL_PERIOD_ID = "PRECALC-58F9-88F5"


class EnrollmentService:
    def __init__(self, enrollment_dao=None, student_dao=None, period_dao=None, parent_dao=None, user_dao=None, quest_dao=None, ltg_conversation_dao=None, conversation_dao=None, ltg_goal_dao=None, jwt: str | None = None, admin_enrollment_dao=None, admin_parent_dao=None, admin_period_dao=None, admin_user_dao=None, admin_ltg_conversation_dao=None, admin_conversation_dao=None, admin_ltg_goal_dao=None, admin_quest_dao=None) -> None:
        self.enrollment_dao = enrollment_dao or EnrollmentDAO(jwt=jwt)
        self.student_dao = student_dao or StudentDAO(jwt=jwt)
        self.period_dao = period_dao or PeriodDAO(jwt=jwt)
        self.parent_dao = parent_dao or ParentDAO(jwt=jwt)
        self.user_dao = user_dao or UserDAO(jwt=jwt)
        self.quest_dao = quest_dao or QuestDAO(jwt=jwt)
        self.ltg_conversation_dao = ltg_conversation_dao or LtgConversationDAO(jwt=jwt)
        self.conversation_dao = conversation_dao or ConversationDAO(jwt=jwt)
        self.ltg_goal_dao = ltg_goal_dao or StudentLongTermGoalDAO(jwt=jwt)
        # Admin DAOs for cross-user reads and FastAPI-only mutations
        self._admin_enrollment_dao = admin_enrollment_dao or EnrollmentDAO()
        self._admin_parent_dao = admin_parent_dao or ParentDAO()
        self._admin_period_dao = admin_period_dao or PeriodDAO()
        self._admin_user_dao = admin_user_dao or UserDAO()
        self._admin_ltg_conversation_dao = admin_ltg_conversation_dao or LtgConversationDAO()
        self._admin_conversation_dao = admin_conversation_dao or ConversationDAO()
        self._admin_ltg_goal_dao = admin_ltg_goal_dao or StudentLongTermGoalDAO()
        self._admin_quest_dao = admin_quest_dao or QuestDAO()

    def enroll_student(self, user_id: str, period_id: str, semester: str = "Fall 2025") -> dict:
        student = self.student_dao.get_student_by_id(user_id)
        if not student:
            raise Exception(f"Student {user_id} not found")

        period = self.period_dao.get_period_by_id(period_id)
        if not period:
            raise Exception(f"Period {period_id} not found")

        enrollment = Enrollment(
            user_id=user_id,
            period_id=period_id,
            semester=semester,
            enrolled_at=datetime.now(timezone.utc).isoformat()
        )
        self.enrollment_dao.add_enrollment(enrollment)
        return {"message": f"Student {user_id} enrolled in {period_id} successfully"}

    def get_enrollments_for_period(self, period_id: str):
        enrollments = self.enrollment_dao.get_enrollments_by_period(period_id)
        period = self.period_dao.get_period_by_id(period_id)
        enriched = []
        for enrollment in enrollments:
            user = self._admin_user_dao.get_by_id(enrollment["user_id"]) if enrollment.get("user_id") else None
            enriched.append({
                **enrollment,
                "first_name": user.get("first_name") if user else None,
                "last_name": user.get("last_name") if user else None,
            })
        return {
            "students": enriched,
            "file_urls": period.get("file_urls", []) if period else []
        }

    def get_enrollment_by_id(self, enrollment_id: str):
        return self.enrollment_dao.get_enrollment_by_id(enrollment_id)

    def delete_enrollment(self, user_id: str, period_id: str, enrolled_at: Optional[str] = None):
        self.enrollment_dao.delete_enrollment(user_id, period_id)
        return {"message": f"Enrollment for {user_id} deleted from {period_id}"}

    def get_student_profile(self, period_id: str, user_id: str):
        try:
            enrollments = self.enrollment_dao.get_enrollments_by_period(period_id)
            if not enrollments:
                return None

            matched_enrollment = next((e for e in enrollments if e.get("user_id") == user_id), None)
            if not matched_enrollment:
                return None

            student = self.student_dao.get_student_by_id(user_id)
            if not student:
                return None

            return {
                "interest": student.get("interest"),
                "strength": student.get("strength"),
                "weakness": student.get("weakness"),
                "learning_style": student.get("learning_style"),
            }
        except Exception as e:
            logger.error("Error in get_student_profile: %s", e, exc_info=True)
            return None

    def get_my_periods(self, user_id: str) -> List[Dict[str, Any]]:
        enrollments = self.enrollment_dao.get_enrollments_by_student(user_id)
        period_ids = [e['period_id'] for e in enrollments]
        ltg_map = self.ltg_goal_dao.get_by_student(user_id)
        periods = {p['period_id']: p for p in self.period_dao.get_periods_by_ids(period_ids)}
        return [
            {
                'period_id': pid,
                'name': periods[pid].get('name', pid),
                'file_urls': periods[pid].get('file_urls', []),
                'long_term_goal': ltg_map.get(pid),
                'is_summer_quest': periods[pid].get('is_summer_quest', False),
            }
            for pid in period_ids
            if pid in periods
        ]

    def get_parent_periods_for_student(self, student_id: str) -> List[Dict[str, Any]]:
        # parent and unenrolled period rows are not visible to a student JWT under RLS;
        # use admin DAOs (no JWT) for these cross-user reads.
        parents = self._admin_parent_dao.get_parents_by_student_id(student_id)
        enrolled = {e['period_id'] for e in self.enrollment_dao.get_enrollments_by_student(student_id)}
        periods = []
        for parent in parents:
            for p in self._admin_period_dao.get_periods_by_owner_id(parent['user_id']):
                if p['period_id'] in enrolled:
                    continue
                if p.get('status') == 'approved':
                    periods.append(p)
        return periods

    def has_teacher_access_to_student(self, teacher_id: str, student_id: str) -> bool:
        teacher_period_ids = {
            p['period_id']
            for p in self._admin_period_dao.get_periods_by_owner_id(teacher_id)
        }
        return any(
            e['period_id'] in teacher_period_ids
            for e in self.enrollment_dao.get_enrollments_by_student(student_id)
        )

    def verify_period_id(self, user_id: str, period_id: str, allow_parent_period: bool = False) -> Any:
        if not period_id:
            raise ValidationError("Missing period ID")

        # Use admin DAO: student is not yet enrolled so user JWT returns None for this period
        period = self._admin_period_dao.get_period_by_id(period_id)
        if not period:
            logger.warning("verify_period_id: period %s not found (user=%s)", period_id, user_id)
            raise NotFoundError("Invalid period ID")

        # Use admin DAO: reading another user's (owner's) row is a cross-user read
        owner = self._admin_user_dao.get_by_id(period["owner_id"])
        if not owner:
            logger.warning("verify_period_id: owner not found for period %s", period_id)
            raise NotFoundError("Invalid period ID")
        if owner["role"] != "teacher" and not allow_parent_period:
            logger.warning(
                "verify_period_id: period %s has owner role %s, not teacher (user=%s)",
                period_id, owner["role"], user_id,
            )
            raise NotFoundError("Invalid period ID")

        if period.get('status') != 'approved':
            logger.warning(
                "verify_period_id: period %s has status=%r, expected 'approved' (user=%s)",
                period_id, period.get('status'), user_id,
            )
            raise NotFoundError("This class is not yet available for enrollment")

        if period.get('archived_at'):
            logger.warning(
                "verify_period_id: period %s is archived (user=%s)", period_id, user_id,
            )
            raise NotFoundError("This class is not available for enrollment")

        student = self.student_dao.get_student_by_id(user_id)
        if not student:
            raise NotFoundError("Student not found")

        existing_enrollments = self.enrollment_dao.get_enrollments_by_student(user_id)
        enrolled_period_ids = [e['period_id'] for e in existing_enrollments]

        if period_id in enrolled_period_ids:
            raise ValidationError(f"You are already enrolled in period {period_id}")

        enrollment = Enrollment(period_id=period_id, user_id=user_id, semester="2024-spring")
        self._admin_enrollment_dao.add_enrollment(enrollment)

        if period_id != TUTORIAL_PERIOD_ID:
            self.cleanup_tutorial_periods(user_id)

        return period

    def unenroll_from_period(self, user_id: str, period_id: str) -> Dict[str, Any]:
        if not period_id:
            raise ValidationError("Missing period ID")

        student = self.student_dao.get_student_by_id(user_id)
        if not student:
            raise NotFoundError("Student not found")

        existing_enrollments = self.enrollment_dao.get_enrollments_by_student(user_id)
        enrolled_period_ids = [e['period_id'] for e in existing_enrollments]
        if period_id not in enrolled_period_ids:
            raise ValidationError(f"You are not enrolled in period {period_id}")

        try:
            self.enrollment_dao.delete_enrollment(user_id, period_id)
        except Exception as e:
            logger.warning("Could not delete enrollment row: %s", e)

        updated_enrollments = [p for p in enrolled_period_ids if p != period_id]

        # All deletes below are on FastAPI-only tables — use admin DAOs
        conversation_id = self._admin_ltg_conversation_dao.delete_conversation(user_id, period_id)
        if conversation_id:
            try:
                self._admin_conversation_dao.delete_conversation(conversation_id)
            except Exception as e:
                logger.warning("Could not delete conversation %s: %s", conversation_id, e)

        self._admin_ltg_goal_dao.delete(user_id, period_id)

        quests = self.quest_dao.get_quests_by_student_and_period(user_id, period_id)
        for q in quests:
            self._admin_quest_dao.delete_quest(q['quest_id'])

        return {
            "message": f"Successfully unenrolled from period {period_id}",
            "period_id": period_id,
            "remaining_enrollments": updated_enrollments,
        }

    def get_enrollments_by_student(self, user_id: str) -> list:
        return self.enrollment_dao.get_enrollments_by_student(user_id)

    def check_enrolled(self, user_id: str, period_id: str) -> None:
        enrollments = self.enrollment_dao.get_enrollments_by_period(period_id)
        if not any(e['user_id'] == user_id for e in enrollments):
            raise ValidationError(f"Student {user_id} is not enrolled in period {period_id}")

    def validate_parent_enrollment_preconditions(
        self, parent_id: str, student_id: str, period_id: str
    ) -> None:
        """Raise ValidationError if student is not linked to parent or is already enrolled."""
        linked = self.parent_dao.get_linked_student_ids(parent_id)
        if student_id not in linked:
            raise ValidationError("Student is not linked to this parent account")
        existing = self.enrollment_dao.get_enrollments_by_student(student_id)
        if any(e["period_id"] == period_id for e in existing):
            raise ValidationError("Student is already enrolled in this class")

    def cleanup_tutorial_periods(self, user_id: str) -> None:
        existing_enrollments = self.enrollment_dao.get_enrollments_by_student(user_id)
        enrolled_period_ids = [e['period_id'] for e in existing_enrollments]
        if TUTORIAL_PERIOD_ID in enrolled_period_ids:
            try:
                self.enrollment_dao.delete_enrollment(user_id, TUTORIAL_PERIOD_ID)
            except Exception as e:
                logger.error("Error removing tutorial enrollment: %s", e)
