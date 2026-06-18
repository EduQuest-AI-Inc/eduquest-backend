from typing import Dict, Any, Optional
from data_access.parent_dao import ParentDAO
from data_access.session_dao import SessionDAO
from data_access.student_dao import StudentDAO
from data_access.teacher_dao import TeacherDAO
from data_access.user_dao import UserDAO
from exceptions.auth_error import AuthError
from exceptions.not_found_error import NotFoundError

class UserService:

    def __init__(self, session_dao=None, student_dao=None, teacher_dao=None, parent_dao=None, user_dao=None, jwt: str | None = None) -> None:
        self.session_dao = session_dao or SessionDAO()
        self.student_dao = student_dao or StudentDAO(jwt=jwt)
        self.teacher_dao = teacher_dao or TeacherDAO(jwt=jwt)
        self.parent_dao = parent_dao or ParentDAO(jwt=jwt)
        self.user_dao = user_dao or UserDAO(jwt=jwt)

    def get_user_profile(self, auth_token: str) -> Dict[str, Any]:
        sessions = self.session_dao.get_sessions_by_auth_token(auth_token)
        if not sessions:
            raise AuthError("Invalid or expired auth token")

        session_info = sessions[0]
        user_id = session_info.get("user_id")
        role = session_info.get("role")

        if not user_id or not role:
            raise AuthError("Session missing user_id or role")

        if role == 'teacher':
            teacher = self.teacher_dao.get_teacher_by_id(user_id)
            if not teacher:
                raise NotFoundError("Teacher not found")
            teacher_profile = teacher
            teacher_profile['role'] = 'teacher'
            return teacher_profile
        elif role == 'student':
            student = self.student_dao.get_student_by_id(user_id)
            if not student:
                raise NotFoundError("Student not found")
            student_profile = student
            student_profile['role'] = 'student'
            return student_profile
        else:
            raise RuntimeError(f"Unrecognized role: {role}")

    def update_tutorial_status(self, user_id: str, completed_tutorial: bool) -> None:
        """Update tutorial status for a student"""
        self.student_dao.update_tutorial_status(user_id, completed_tutorial)

    def get_tutorial_status(self, user_id: str) -> bool:
        """Get tutorial status for a student"""
        return self.student_dao.get_tutorial_status(user_id)

    def needs_tutorial(self, user_id: str) -> bool:
        """Check if student needs tutorial"""
        return self.student_dao.needs_tutorial(user_id)

    def get_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        return self.user_dao.get_by_id(user_id)

    def get_student_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        return self.student_dao.get_student_by_id(user_id)

    def get_teacher_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        return self.teacher_dao.get_teacher_by_id(user_id)

    def get_parent_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        return self.parent_dao.get_parent_by_id(user_id)

