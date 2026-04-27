from passlib.context import CryptContext
from werkzeug.security import check_password_hash as _werkzeug_check

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
_LEGACY_PREFIXES = ("pbkdf2:", "scrypt:")


def generate_password_hash(password: str) -> str:
    return _pwd_context.hash(password)


def check_password_hash(hashed: str, password: str) -> bool:
    if hashed.startswith(_LEGACY_PREFIXES):
        return _werkzeug_check(hashed, password)
    return _pwd_context.verify(password, hashed)


def _is_legacy_hash(hashed: str) -> bool:
    return hashed.startswith(_LEGACY_PREFIXES)

from data_access.user_dao import UserDAO
from data_access.student_dao import StudentDAO
from data_access.teacher_dao import TeacherDAO
from data_access.parent_dao import ParentDAO
from models.student import Student
from models.teacher import Teacher
from models.parent import Parent
from .password_policy import validate_password

user_dao = UserDAO()
student_dao = StudentDAO()
teacher_dao = TeacherDAO()
parent_dao = ParentDAO()


def register_user(username: str, password: str, role: str, first_name: str = '', last_name: str = '', email: str = '', grade: str = None) -> dict:
    """Register a new user (student, teacher, or parent)."""
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
        grade=grade,
    )
    student_dao.add_student(student)
    return {"success": True}


def authenticate_user(username: str, password: str, role: str) -> bool:
    user = user_dao.get_by_id(username)
    if not user or user.get('role') != role:
        return False
    stored_hash = user['password']
    if not check_password_hash(stored_hash, password):
        return False
    if _is_legacy_hash(stored_hash):
        try:
            user_dao.update(username, {"password": generate_password_hash(password)})
        except Exception:
            pass
    return True
