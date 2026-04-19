import os
import secrets
import string
from datetime import datetime, timedelta, timezone
from constants.timeouts import INVITE_EXPIRY_HOURS

if os.getenv('USE_SUPABASE', 'false').lower() == 'true':
    from data_access.supabase.period_dao import PeriodDAO
    from data_access.supabase.parent_dao import ParentDAO
    from data_access.supabase.parent_invite_dao import ParentInviteDAO
    from data_access.supabase.student_dao import StudentDAO
else:
    from data_access.period_dao import PeriodDAO
    from data_access.parent_dao import ParentDAO
    from data_access.parent_invite_dao import ParentInviteDAO
    from data_access.student_dao import StudentDAO

from models.period import Period
from models.parent_invite import ParentInvite
from routes.teacher.teacher_service import TeacherService

_INVITE_ALPHABET = string.ascii_uppercase + string.digits


class ParentService:
    def __init__(self):
        self.period_dao = PeriodDAO()
        self.parent_dao = ParentDAO()
        self.invite_dao = ParentInviteDAO()
        self.student_dao = StudentDAO()
        self._teacher_service = TeacherService()

    # -- Period helpers -------------------------------------------------------

    def create_period(self, course: str, parent_id: str, vector_store_id: str, file_urls: list) -> dict:
        period_id = self._teacher_service.generate_period_id(course)

        existing = self.period_dao.get_period_by_id(period_id)
        attempts = 0
        while existing and attempts < 5:
            period_id = self._teacher_service.generate_period_id(course)
            existing = self.period_dao.get_period_by_id(period_id)
            attempts += 1

        if existing:
            raise ValueError("Unable to generate unique period ID")

        new_period = Period(
            period_id=period_id,
            course=course,
            owner_id=parent_id,
            owner_type="parent",
            vector_store_id=vector_store_id,
            file_urls=file_urls,
            teacher_id=None,
            parent_id=parent_id,
        )
        self.period_dao.add_period(new_period)
        return new_period.to_item()

    def get_periods_by_parent(self, parent_id: str) -> list:
        periods = self.period_dao.get_periods_by_parent_id(parent_id)
        result = []
        for p in periods:
            item = p if isinstance(p, dict) else p.model_dump()
            result.append({
                "period_id": item["period_id"],
                "course": item["course"],
                "file_urls": item.get("file_urls", []),
            })
        return result

    def update_period_files(self, period_id: str, file_urls: list) -> None:
        self.period_dao.update_period(period_id, {"file_urls": file_urls})

    # -- Invite helpers -------------------------------------------------------

    def generate_invite(self, parent_id: str) -> dict:
        code = ''.join(secrets.choice(_INVITE_ALPHABET) for _ in range(8))
        expires_at = (datetime.now(timezone.utc) + timedelta(hours=INVITE_EXPIRY_HOURS)).isoformat()
        invite = ParentInvite(code=code, parent_id=parent_id, expires_at=expires_at)
        self.invite_dao.create_invite(invite)
        return {"code": code, "expires_at": expires_at}

    # -- Student helpers ------------------------------------------------------

    def get_linked_students(self, parent_id: str) -> list:
        parent = self.parent_dao.get_parent_by_id(parent_id)
        if not parent:
            return []
        linked_ids = parent.get("linked_student_ids", [])
        students = []
        for student_id in linked_ids:
            student = self.student_dao.get_student_by_id(student_id)
            if student:
                students.append({
                    "student_id": student_id,
                    "first_name": student.get("first_name", ""),
                    "last_name": student.get("last_name", ""),
                    "grade": student.get("grade", ""),
                    "email": student.get("email", ""),
                })
        return students
