import hashlib
import hmac
import bcrypt
from typing import Optional

_LEGACY_PREFIXES = ("pbkdf2:", "scrypt:")


def check_werkzeug_pbkdf2(hashed: str, password: str) -> bool:
    # werkzeug pbkdf2 format: pbkdf2:<method>:<iterations>$<salt>$<hash>
    try:
        # Split on "$" first to separate the metadata header from salt and hash
        meta, salt, expected = hashed.split("$", 2)
        # meta = "pbkdf2:<method>:<iterations>"
        _, method, iterations_str = meta.split(":", 2)
        dk = hashlib.pbkdf2_hmac(method, password.encode(), salt.encode(), int(iterations_str))
        return hmac.compare_digest(dk.hex(), expected)
    except Exception:
        return False


def generate_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def check_password_hash(hashed: str, password: str) -> bool:
    if hashed.startswith(_LEGACY_PREFIXES):
        return check_werkzeug_pbkdf2(hashed, password)
    return bcrypt.checkpw(password.encode(), hashed.encode())


def _is_legacy_hash(hashed: str) -> bool:
    return hashed.startswith(_LEGACY_PREFIXES)

import logging

from data_access.session_dao import SessionDAO
from data_access.user_dao import UserDAO
from data_access.student_dao import StudentDAO
from data_access.teacher_dao import TeacherDAO
from data_access.parent_dao import ParentDAO
from models.student import Student
from models.teacher import Teacher
from models.parent import Parent
from .password_policy import validate_password
from .supabase_auth_service import SupabaseAuthService

logger = logging.getLogger(__name__)


class AuthService:
    def __init__(
        self,
        user_dao=None,
        session_dao=None,
        student_dao=None,
        teacher_dao=None,
        parent_dao=None,
        supabase_auth_service=None,
    ) -> None:
        self.user_dao = user_dao or UserDAO()
        self.session_dao = session_dao or SessionDAO()
        self.student_dao = student_dao or StudentDAO()
        self.teacher_dao = teacher_dao or TeacherDAO()
        self.parent_dao = parent_dao or ParentDAO()
        self.supabase_auth_service = supabase_auth_service or SupabaseAuthService()

    def register_user(self, username: str, password: str, role: str, first_name: str = '', last_name: str = '', email: str = '', grade: Optional[str] = None, phone_number: Optional[str] = None, age_band: Optional[str] = None) -> dict:
        is_valid, error_msg = validate_password(password)
        if not is_valid:
            return {"success": False, "error": error_msg}

        if self.user_dao.get_by_id(username):
            return {"success": False, "error": "Username already exists"}

        hashed_pw = generate_password_hash(password)

        if role == 'teacher':
            teacher = Teacher(
                user_id=username,
                password=hashed_pw,
                first_name=first_name,
                last_name=last_name,
                email=email,
                phone_number=phone_number,
                pilot_approved=False,
            )
            self.teacher_dao.add_teacher(teacher)
            try:
                self.supabase_auth_service.provision_user(username, email, password, role)
            except Exception:  # provision_user already swallows, but guard defensively
                logger.warning("Supabase Auth provision call raised for %s", username, exc_info=True)
            return {"success": True}

        if role == 'parent':
            parent = Parent(
                user_id=username,
                password=hashed_pw,
                first_name=first_name,
                last_name=last_name,
                email=email,
                phone_number=phone_number,
            )
            self.parent_dao.add_parent(parent)
            try:
                self.supabase_auth_service.provision_user(username, email, password, role)
            except Exception:  # provision_user already swallows, but guard defensively
                logger.warning("Supabase Auth provision call raised for %s", username, exc_info=True)
            return {"success": True}

        student = Student(
            user_id=username,
            password=hashed_pw,
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone_number=phone_number,
            grade=int(grade) if grade is not None else None,
            age_band=age_band,
            age_signal_source='self_screen',
            compliance_status='active' if age_band == '18_plus' else 'blocked',
        )
        self.student_dao.add_student(student)
        try:
            self.supabase_auth_service.provision_user(username, email, password, role)
        except Exception:  # provision_user already swallows, but guard defensively
            logger.warning("Supabase Auth provision call raised for %s", username, exc_info=True)
        return {"success": True}

    def get_user_by_email(self, email: str):
        return self.user_dao.get_by_email(email)

    def get_user_by_id(self, user_id: str):
        return self.user_dao.get_by_id(user_id)

    def add_session(self, session) -> None:
        self.session_dao.add_session(session)

    def get_student_by_id(self, user_id: str):
        return self.student_dao.get_student_by_id(user_id)

    def backfill_supabase_auth_id(self, user_id: str, plaintext_password: str, role: str) -> None:
        """
        Called after successful login. If supabase_auth_id is not yet set, provisions
        a Supabase Auth entry using the plaintext password from login. Idempotent.
        """
        user = self.user_dao.get_by_id(user_id)
        if not user or user.get("supabase_auth_id"):
            return
        email = user.get("email", "")
        self.supabase_auth_service.provision_user(user_id, email, plaintext_password, role)

    def authenticate_user(self, username: str, password: str, role: str) -> bool:
        user = self.user_dao.get_by_id(username)
        if not user:
            logger.warning("authenticate_user: user not found: %s", username)
            return False
        if user.get('role') != role:
            logger.warning("authenticate_user: role mismatch for %s: db=%r, got=%r", username, user.get('role'), role)
            return False
        if user.get('login_disabled'):
            logger.warning("authenticate_user: login_disabled for %s", username)
            return False
        if role == 'student':
            student = self.student_dao.get_student_by_id(username)
            if not student or student.get('compliance_status') in {
                'quarantined_age_review', 'provisioning', 'blocked'
            }:
                logger.warning("authenticate_user: student compliance gate blocked %s", username)
                return False
        stored_hash = user['password']
        if not check_password_hash(stored_hash, password):
            logger.warning("authenticate_user: password mismatch for %s (hash prefix: %s)", username, stored_hash[:10])
            return False
        if _is_legacy_hash(stored_hash):
            try:
                self.user_dao.update(username, {"password": generate_password_hash(password)})
            except Exception:
                logger.warning("legacy password hash upgrade failed", exc_info=True)
        return True


# Transitional shims — router callers unchanged; follow-on PR will inject AuthService via Depends()
_auth_service = AuthService()


def register_user(username: str, password: str, role: str, first_name: str = '', last_name: str = '', email: str = '', grade: Optional[str] = None, phone_number: Optional[str] = None, age_band: Optional[str] = None) -> dict:
    return _auth_service.register_user(username, password, role, first_name, last_name, email, grade, phone_number, age_band)


def get_user_by_email(email: str):
    return _auth_service.get_user_by_email(email)


def get_user_by_id(user_id: str):
    return _auth_service.get_user_by_id(user_id)


def add_session(session) -> None:
    _auth_service.add_session(session)


def get_student_by_id(user_id: str):
    return _auth_service.get_student_by_id(user_id)


def authenticate_user(username: str, password: str, role: str) -> bool:
    return _auth_service.authenticate_user(username, password, role)


def backfill_supabase_auth_id(user_id: str, plaintext_password: str, role: str) -> None:
    return _auth_service.backfill_supabase_auth_id(user_id, plaintext_password, role)
