import logging
import os
import secrets

import httpx
from fastapi import HTTPException

from data_access.user_dao import UserDAO
from services.auth.auth_service import AuthService
from services.auth.supabase_auth_service import SupabaseAuthService
from services.billing.membership_service import MembershipService

logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL", "")


class OAuthService:
    def __init__(self, user_dao=None, auth_service=None, supabase_auth_service=None, membership_service=None) -> None:
        self.user_dao = user_dao or UserDAO()
        self.auth_service = auth_service or AuthService()
        self.supabase_auth_service = supabase_auth_service or SupabaseAuthService()
        self.membership_service = membership_service or MembershipService()

    def complete_oauth(
        self,
        access_token: str,
        role: str,
        grade: str | None = None,
        trial_confirmed: bool | None = None,
    ) -> dict:
        supabase_user = self._verify_supabase_token(access_token)
        email: str = (supabase_user.get("email") or "").strip().lower()
        if not email:
            raise HTTPException(status_code=400, detail="OAuth provider did not supply an email address.")

        existing = self.user_dao.get_by_email(email)

        if existing:
            if existing.get("role") != role:
                raise HTTPException(
                    status_code=400,
                    detail=f"This email is already registered as a {existing['role']}. Please select that role to sign in.",
                )
            username: str = existing["user_id"]
        else:
            if role == "student":
                raise HTTPException(
                    status_code=403,
                    detail="New student OAuth signup is unavailable until student authorization is completed.",
                )
            if role == "student" and not grade:
                raise HTTPException(status_code=400, detail="grade is required for students.")
            if role in ("teacher", "parent") and not trial_confirmed:
                raise HTTPException(status_code=400, detail="trial_confirmed is required for teacher/parent accounts.")

            meta: dict = supabase_user.get("user_metadata") or {}
            first_name = (meta.get("given_name") or meta.get("full_name", "").split()[0] if meta.get("full_name") else "").strip() or "User"
            last_name_parts = (meta.get("family_name") or " ".join(meta.get("full_name", "").split()[1:])).strip()
            last_name = last_name_parts or ""

            username = self._generate_username(email)
            # token_hex(16) → 32 hex chars; passes policy (10+ chars, letters + digits)
            random_password = secrets.token_hex(16)

            result = self.auth_service.register_user(
                username=username,
                password=random_password,
                role=role,
                first_name=first_name,
                last_name=last_name,
                email=email,
                grade=grade if role == "student" else None,
            )
            if not result.get("success"):
                # Retry once with a new username in case of collision
                username = self._generate_username(email)
                result = self.auth_service.register_user(
                    username=username,
                    password=secrets.token_hex(16),
                    role=role,
                    first_name=first_name,
                    last_name=last_name,
                    email=email,
                    grade=grade if role == "student" else None,
                )
                if not result.get("success"):
                    raise HTTPException(status_code=500, detail="Failed to create account. Please try again.")

            if role in ("teacher", "parent"):
                try:
                    self.membership_service.start_trial_if_eligible(username, role)
                except Exception as exc:
                    logger.warning("Trial creation failed for OAuth user %s: %s", username, exc, exc_info=True)

        supabase_auth_uuid: str = supabase_user.get("id", "")
        if supabase_auth_uuid:
            self.supabase_auth_service.store_oauth_auth_id(username, supabase_auth_uuid, role)

        needs_profile = False
        if role == "student":
            student = self.auth_service.get_student_by_id(username)
            if student and not all([
                student.get("strength"),
                student.get("weakness"),
                student.get("interest"),
                student.get("learning_style"),
            ]):
                needs_profile = True

        return {"username": username, "needs_profile": needs_profile}

    def _verify_supabase_token(self, access_token: str) -> dict:
        if not SUPABASE_URL:
            raise HTTPException(status_code=500, detail="Supabase URL not configured.")
        try:
            resp = httpx.get(
                f"{SUPABASE_URL}/auth/v1/user",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=10,
            )
        except httpx.RequestError as exc:
            logger.error("Supabase token verification request failed: %s", exc, exc_info=True)
            raise HTTPException(status_code=502, detail="Could not verify OAuth token.")

        if resp.status_code != 200:
            raise HTTPException(status_code=401, detail="Invalid or expired OAuth token.")

        return resp.json()

    def _generate_username(self, email: str) -> str:
        prefix = email.split("@")[0]
        # Keep only alphanumeric and underscores, max 16 chars
        safe = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in prefix)[:16]
        suffix = secrets.token_hex(2)  # 4 hex chars
        return f"{safe}_{suffix}"
