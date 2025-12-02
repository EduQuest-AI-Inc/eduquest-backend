from werkzeug.security import generate_password_hash, check_password_hash
from data_access.student_dao import StudentDAO
from data_access.teacher_dao import TeacherDAO
from data_access.admin_dao import AdminDAO
from data_access.waitlist_dao import WaitlistDAO
from models.student import Student
from models.teacher import Teacher
from models.administrator import Administrator

student_dao = StudentDAO()
teacher_dao = TeacherDAO()
admin_dao = AdminDAO()
waitlist_dao = WaitlistDAO()

def register_user(username: str, password: str, role: str, first_name: str = '', last_name: str = '', email: str = '', grade: str = None, school_id: str = None, waitlist_code: str = None) -> dict:
    if waitlist_code:
        validation = waitlist_dao.validate_code(waitlist_code)
        if not validation.get("valid"):
            return {"success": False, "error": validation.get("error")}

    if role == 'admin':
        if not school_id:
            return {"success": False, "error": "School ID is required for administrators"}
        existing = admin_dao.get_admin_by_id(username)
        if existing:
            return {"success": False, "error": "Username already exists"}
        hashed_pw = generate_password_hash(password)
        admin = Administrator(admin_id=username, password=hashed_pw, first_name=first_name, last_name=last_name, email=email, school_id=school_id)
        admin_dao.add_admin(admin)
        if waitlist_code:
            waitlist_dao.mark_code_as_used(waitlist_code, username)
        return {"success": True}
    elif role == 'teacher':
        existing = teacher_dao.get_teacher_by_id(username)
        if existing:
            return {"success": False, "error": "Username already exists"}
        hashed_pw = generate_password_hash(password)
        teacher = Teacher(teacher_id=username, password=hashed_pw, first_name=first_name, last_name=last_name, email=email)
        teacher_dao.add_teacher(teacher)
        if waitlist_code:
            waitlist_dao.mark_code_as_used(waitlist_code, username)
        return {"success": True}
    else:
        existing = student_dao.get_student_by_id(username)
        if existing:
            return {"success": False, "error": "Username already exists"}
        hashed_pw = generate_password_hash(password)
        student = Student(student_id=username, password=hashed_pw, first_name=first_name, last_name=last_name, email=email, grade=grade)
        student_dao.add_student(student)
        if waitlist_code:
            waitlist_dao.mark_code_as_used(waitlist_code, username)
        return {"success": True}

def authenticate_user(username: str, password: str, role: str) -> bool:
    if role == 'admin':
        user = admin_dao.get_admin_by_id(username)
        if not user:
            return False
        return check_password_hash(user['password'], password)
    elif role == 'teacher':
        user = teacher_dao.get_teacher_by_id(username)
        if not user:
            return False
        return check_password_hash(user['password'], password)
    else:
        user = student_dao.get_student_by_id(username)
        if not user:
            return False
        return check_password_hash(user['password'], password)