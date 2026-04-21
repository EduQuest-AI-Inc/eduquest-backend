import logging
from data_access.supabase.enrollment_dao import EnrollmentDAO
from data_access.supabase.student_dao import StudentDAO
from data_access.supabase.period_dao import PeriodDAO

from models.enrollment import Enrollment
from datetime import datetime

logger = logging.getLogger(__name__)


class EnrollmentService:
    def __init__(self):
        self.enrollment_dao = EnrollmentDAO()
        self.student_dao = StudentDAO()
        self.period_dao = PeriodDAO()

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
            enrolled_at=datetime.utcnow().isoformat()
        )
        self.enrollment_dao.add_enrollment(enrollment)
        return {"message": f"Student {user_id} enrolled in {period_id} successfully"}

    def get_enrollments_for_period(self, period_id: str):
        enrollments = self.enrollment_dao.get_enrollments_by_period(period_id)
        period = self.period_dao.get_period_by_id(period_id)
        return {
            "students": enrollments,
            "file_urls": period.get("file_urls", []) if period else []
        }

    def get_enrollment_by_id(self, enrollment_id: str):
        return self.enrollment_dao.get_enrollment_by_id(enrollment_id)

    def delete_enrollment(self, user_id: str, period_id: str, enrolled_at: str = None):
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
