# auth_service.py
# Handles user registration and authentication logic
from werkzeug.security import generate_password_hash, check_password_hash
import os
if os.getenv('USE_SUPABASE', 'false').lower() == 'true':
    from data_access.supabase.student_dao import StudentDAO
    from data_access.supabase.teacher_dao import TeacherDAO
    from data_access.supabase.parent_dao import ParentDAO
else:
    from data_access.student_dao import StudentDAO
    from data_access.teacher_dao import TeacherDAO
    from data_access.parent_dao import ParentDAO
from models.student import Student
from models.teacher import Teacher
from models.parent import Parent
from .password_policy import validate_password

student_dao = StudentDAO()
teacher_dao = TeacherDAO()
parent_dao = ParentDAO()


def register_user(username: str, password: str, role: str, first_name: str = '', last_name: str = '', email: str = '', email_lc: str = '', grade: str = None) -> dict:
    """
    Register a new user (student, teacher, or parent).
    Teachers are created with pilot_approved=False by default.
    email_lc is the canonical lowercase email for consistent lookups.
    """
    # Validate password against policy
    is_valid, error_msg = validate_password(password)
    if not is_valid:
        return {"success": False, "error": error_msg}

    if role == 'teacher':
        existing = teacher_dao.get_teacher_by_id(username)
        if existing:
            return {"success": False, "error": "Username already exists"}
        hashed_pw = generate_password_hash(password)
        teacher = Teacher(
            teacher_id=username,
            password=hashed_pw,
            first_name=first_name,
            last_name=last_name,
            email=email,
            email_lc=email_lc,
            pilot_approved=False  # Teachers start unapproved for pilot study
        )
        teacher_dao.add_teacher(teacher)
        return {"success": True}

    elif role == 'parent':
        existing = parent_dao.get_parent_by_id(username)
        if existing:
            return {"success": False, "error": "Username already exists"}
        hashed_pw = generate_password_hash(password)
        parent = Parent(
            parent_id=username,
            password=hashed_pw,
            first_name=first_name,
            last_name=last_name,
            email=email,
            email_lc=email_lc,
        )
        parent_dao.add_parent(parent)
        return {"success": True}

    else:
        existing = student_dao.get_student_by_id(username)
        if existing:
            return {"success": False, "error": "Username already exists"}
        hashed_pw = generate_password_hash(password)
        student = Student(
            student_id=username,
            password=hashed_pw,
            first_name=first_name,
            last_name=last_name,
            email=email,
            email_lc=email_lc,
            grade=grade
        )
        student_dao.add_student(student)
        return {"success": True}


def authenticate_user(username: str, password: str, role: str) -> bool:
    if role == 'teacher':
        user = teacher_dao.get_teacher_by_id(username)
        if not user:
            return False
        return check_password_hash(user['password'], password)
    elif role == 'parent':
        user = parent_dao.get_parent_by_id(username)
        if not user:
            return False
        return check_password_hash(user['password'], password)
    else:
        user = student_dao.get_student_by_id(username)
        if not user:
            return False
        return check_password_hash(user['password'], password)
