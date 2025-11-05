# auth_service.py
# Handles user registration and authentication logic
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import create_access_token
from data_access.student_dao import StudentDAO
from data_access.teacher_dao import TeacherDAO
from data_access.session_dao import SessionDAO
from models.student import Student
from models.teacher import Teacher
from models.session import Session

student_dao = StudentDAO()
teacher_dao = TeacherDAO()
session_dao = SessionDAO()

def register_user(username: str, password: str, role: str, first_name: str = '', last_name: str = '', email: str = '', grade: str = None) -> bool:
    if role == 'teacher':
        existing = teacher_dao.get_teacher_by_id(username)
        if existing:
            return False
        hashed_pw = generate_password_hash(password)
        teacher = Teacher(teacher_id=username, password=hashed_pw, first_name=first_name, last_name=last_name, email=email)
        teacher_dao.add_teacher(teacher)
        return True
    else:
        existing = student_dao.get_student_by_id(username)
        if existing:
            return False
        hashed_pw = generate_password_hash(password)
        student = Student(student_id=username, password=hashed_pw, first_name=first_name, last_name=last_name, email=email, grade=grade)
        student_dao.add_student(student)
        return True

def authenticate_user(username: str, password: str, role: str) -> bool:
    if role == 'teacher':
        user = teacher_dao.get_teacher_by_id(username)
        if not user:
            return False
        return check_password_hash(user['password'], password)
    else:
        user = student_dao.get_student_by_id(username)
        if not user:
            return False
        return check_password_hash(user['password'], password)

def create_user_session(username: str, role: str) -> str:
    """Create JWT token and session for authenticated user"""
    access_token = create_access_token(identity=username)
    session = Session(auth_token=access_token, user_id=username, role=role)
    session_dao.add_session(session)
    return access_token