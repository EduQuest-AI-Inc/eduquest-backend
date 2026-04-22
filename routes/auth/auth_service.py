from werkzeug.security import generate_password_hash, check_password_hash

from data_access.supabase.user_dao import UserDAO
from data_access.supabase.student_dao import StudentDAO
from data_access.supabase.teacher_dao import TeacherDAO
from data_access.supabase.parent_dao import ParentDAO
from models.student import Student
from models.teacher import Teacher
from models.parent import Parent
from .password_policy import validate_password

user_dao = UserDAO()
student_dao = StudentDAO()
teacher_dao = TeacherDAO()
parent_dao = ParentDAO()


def register_user(username: str, password: str, role: str, first_name: str = '', last_name: str = '', email: str = '', email_lc: str = '', grade: str = None) -> dict:
    """
    Register a new user (student, teacher, or parent).
    Teachers are created with pilot_approved=False by default.
    email_lc is the canonical lowercase email for consistent lookups.
    """
    is_valid, error_msg = validate_password(password)
    if not is_valid:
        return {"success": False, "error": error_msg}

    if user_dao.get_by_id(username):
        return {"success": False, "error": "Username already exists"}

    hashed_pw = generate_password_hash(password)

    if role == 'teacher':
        teacher = Teacher(
            user_id=username,
            password=hashed_pw,
            first_name=first_name,
            last_name=last_name,
            email=email,
            email_lc=email_lc,
            pilot_approved=False,
        )
        teacher_dao.add_teacher(teacher)
        return {"success": True}

    if role == 'parent':
        parent = Parent(
            user_id=username,
            password=hashed_pw,
            first_name=first_name,
            last_name=last_name,
            email=email,
            email_lc=email_lc,
        )
        parent_dao.add_parent(parent)
        return {"success": True}

    # student
    student = Student(
        user_id=username,
        password=hashed_pw,
        first_name=first_name,
        last_name=last_name,
        email=email,
        email_lc=email_lc,
        grade=grade,
    )
    student_dao.add_student(student)
    return {"success": True}


def authenticate_user(username: str, password: str, role: str) -> bool:
    user = user_dao.get_by_id(username)
    if not user or user.get('role') != role:
        return False
    return check_password_hash(user['password'], password)
