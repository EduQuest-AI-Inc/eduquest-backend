from typing import Dict, Any
from models.student import Student
from models.teacher import Teacher

from data_access.session_dao import SessionDAO
from data_access.student_dao import StudentDAO
from data_access.teacher_dao import TeacherDAO

class UserService:

    def __init__(self):
        self.session_dao = SessionDAO()
        self.student_dao = StudentDAO()
        self.teacher_dao = TeacherDAO()

    def get_user_profile(self, auth_token: str) -> Dict[str, Any]:
        sessions = self.session_dao.get_sessions_by_auth_token(auth_token)
        if not sessions:
            raise ValueError("Invalid or expired auth token")

        session_info = sessions[0]
        user_id = session_info.get("user_id")
        role = session_info.get("role")

        if not user_id or not role:
            raise ValueError("Session missing user_id or role")

        if role == 'teacher':
            teacher = self.teacher_dao.get_teacher_by_id(user_id)
            if not teacher:
                raise ValueError("Teacher not found")
            teacher_profile = teacher
            teacher_profile['role'] = 'teacher'
            return teacher_profile
        elif role == 'student':
            student = self.student_dao.get_student_by_id(user_id)
            if not student:
                raise ValueError("Student not found")
            student_profile = student
            student_profile['role'] = 'student'
            return student_profile
        else:
            raise ValueError(f"Unrecognized role: {role}")

    def update_tutorial_status(self, student_id: str, completed_tutorial: bool):
        """Update tutorial status for a student"""
        self.student_dao.update_tutorial_status(student_id, completed_tutorial)

    def get_tutorial_status(self, student_id: str) -> bool:
        """Get tutorial status for a student"""
        return self.student_dao.get_tutorial_status(student_id)

    def needs_tutorial(self, student_id: str) -> bool:
        """Check if student needs tutorial"""
        return self.student_dao.needs_tutorial(student_id)

