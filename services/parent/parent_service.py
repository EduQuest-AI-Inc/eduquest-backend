import secrets
import string
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from constants.timeouts import INVITE_EXPIRY_HOURS
from data_access.parent_dao import ParentDAO
from data_access.parent_invite_dao import ParentInviteDAO
from data_access.student_dao import StudentDAO
from data_access.user_dao import UserDAO

from models.parent_invite import ParentInvite
from models.student import Student
from services.auth.auth_service import generate_password_hash

_INVITE_ALPHABET = string.ascii_uppercase + string.digits


class ParentService:
    def __init__(self) -> None:
        self.parent_dao = ParentDAO()
        self.invite_dao = ParentInviteDAO()
        self.student_dao = StudentDAO()
        self.user_dao = UserDAO()

    # -- Invite helpers -------------------------------------------------------

    def generate_invite(self, user_id: str) -> dict:
        code = ''.join(secrets.choice(_INVITE_ALPHABET) for _ in range(8))
        expires_at = (datetime.now(timezone.utc) + timedelta(hours=INVITE_EXPIRY_HOURS)).isoformat()
        invite = ParentInvite(code=code, user_id=user_id, expires_at=expires_at)
        self.invite_dao.create_invite(invite)
        return {"code": code, "expires_at": expires_at}

    def accept_invite(self, student_id: str, code: str) -> dict:
        """Link a student to a parent via a single-use invite code."""
        invite = self.invite_dao.get_invite_by_code(code)
        if not invite:
            raise ValueError("Invalid invite code")
        if invite.get("used"):
            raise ValueError("Invite code has already been used")

        expires_at_str = invite.get("expires_at", "")
        try:
            expires_at = datetime.fromisoformat(expires_at_str)
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            raise ValueError("Invalid invite data")

        if datetime.now(timezone.utc) > expires_at:
            raise ValueError("Invite code has expired")

        parent_id = invite.get("user_id")
        if not parent_id:
            raise ValueError("Invite data missing user_id")
        parent = self.parent_dao.get_parent_by_id(parent_id)
        if not parent:
            raise ValueError("Parent account not found")

        linked_ids = list(parent.get("linked_student_ids") or [])
        if student_id in linked_ids:
            return {"message": "Already linked to this parent", "already_linked": True}

        linked_ids.append(student_id)
        vpc_verified_at = datetime.now(timezone.utc).isoformat()
        self.parent_dao.update_parent(parent_id, {
            "linked_student_ids": linked_ids,
            "vpc_verified_at": vpc_verified_at,
        })
        self.invite_dao.mark_used(code)

        return {
            "message": "Successfully linked to parent account",
            "student_id": student_id,
            "parent_id": parent_id,
            "vpc_verified_at": vpc_verified_at,
        }

    def create_student_profile(self, parent_id: str, name: str, grade: int, interests: list) -> dict:
        """Create a parent-managed student identity with login disabled.

        The student record is stable: the same user_id is used when the account
        is later claimed and login credentials are attached.
        """
        student_id = str(uuid4())
        # Synthetic email satisfies the DB UNIQUE constraint; it is never used for login
        synthetic_email = f"child_{uuid4().hex[:8]}@internal.eduquestai.org"
        # Random bcrypt hash — no real password will ever match; login is also
        # blocked via login_disabled=True before bcrypt is checked
        unusable_hash = generate_password_hash(secrets.token_hex(32))

        student = Student(
            user_id=student_id,
            first_name=name,
            last_name="",
            email=synthetic_email,
            password=unusable_hash,
            login_disabled=True,
            role="student",
            grade=grade,
            interest=interests,
            account_status="parent_managed",
            created_by_parent_id=parent_id,
        )
        self.student_dao.add_student(student)

        parent = self.parent_dao.get_parent_by_id(parent_id)
        linked_ids = list((parent or {}).get("linked_student_ids") or [])
        linked_ids.append(student_id)
        try:
            self.parent_dao.update_parent(parent_id, {"linked_student_ids": linked_ids})
        except Exception:
            # Compensating delete so we don't orphan the student record
            self.student_dao.delete_student(student_id)
            raise

        return {"user_id": student_id, "name": name, "grade": grade, "interests": interests}

    # -- Student helpers ------------------------------------------------------

    def get_linked_student_ids(self, user_id: str) -> list:
        return self.parent_dao.get_linked_student_ids(user_id)

    def get_linked_students(self, user_id: str) -> list:
        linked_ids = self.parent_dao.get_linked_student_ids(user_id)
        students = []
        for student_id in linked_ids:
            student = self.student_dao.get_student_by_id(student_id)
            if student:
                email = student.get("email", "")
                students.append({
                    "user_id": student_id,
                    "first_name": student.get("first_name", ""),
                    "last_name": student.get("last_name", ""),
                    "grade": student.get("grade", ""),
                    "email": "" if email.endswith("@internal.eduquestai.org") else email,
                    "interest": student.get("interest") or [],
                })
        return students
