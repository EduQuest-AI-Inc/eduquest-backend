import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from constants.timeouts import JWT_EXPIRY_HOURS
from data_access.config import get_admin_supabase_client as get_supabase_client
from responses.auth import (
    LoginResponse,
    OAuthCompleteResponse,
    PasswordResetConfirmResponse,
    PasswordResetRequestResponse,
    SignupResponse,
)
from services.auth.auth_service import (
    authenticate_user,
    backfill_supabase_auth_id,
    get_student_by_id,
    get_user_by_email,
    get_user_by_id,
    register_user,
)
from services.auth.oauth_service import OAuthService
from services.auth.supabase_auth_service import SupabaseAuthService
from services.parent.parent_service import ParentService
from services.auth.password_reset_service import get_password_reset_service
from utils.validation_utils import get_client_ip

logger = logging.getLogger(__name__)
router = APIRouter()

# Dead code until Phase 6 — kept to avoid breaking any external callers during rollout.
JWT_SECRET = os.getenv("JWT_SECRET_KEY", "fallback-secret")
JWT_ALGORITHM = "HS256"

_parent_service = ParentService()
_oauth_service = OAuthService()
password_reset_service = get_password_reset_service()


def _mint_token(username: str, role: str) -> str:
    payload = {
        "sub": username,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRY_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


# ---------------------------------------------------------------------------
# Signup
# ---------------------------------------------------------------------------

class SignupRequest(BaseModel):
    username: str
    password: str
    role: str
    first_name: str
    last_name: str
    email: str
    grade: Optional[str] = None
    phone_number: Optional[str] = None
    invite_code: Optional[str] = None
    # Required confirmation for parent/teacher accounts: explicit acknowledgement
    # that they are starting the 14-day no-card trial. The frontend renders the
    # trial-terms screen and only sets this to True after the user confirms.
    trial_confirmed: Optional[bool] = None


@router.post("/signup", status_code=201, response_model=SignupResponse)
def signup(body: SignupRequest):
    valid_roles = {"student", "teacher", "parent"}
    if body.role not in valid_roles:
        raise HTTPException(status_code=400, detail=f"Invalid role. Must be one of: {', '.join(valid_roles)}")
    if body.role == "student" and not body.grade:
        raise HTTPException(status_code=400, detail="grade is required for students")
    if body.role in ("teacher", "parent") and not body.trial_confirmed:
        raise HTTPException(
            status_code=400,
            detail="trial_confirmed is required for parent/teacher signups",
        )

    normalized_email = body.email.strip().lower()
    if get_user_by_email(normalized_email):
        raise HTTPException(status_code=409, detail="Email address already in use")

    result = register_user(
        body.username, body.password, body.role,
        body.first_name, body.last_name, normalized_email,
        body.grade if body.role == "student" else None,
        body.phone_number,
    )
    if not result.get("success"):
        error_message = result.get("error", "Registration failed")
        status = 409 if "already exists" in error_message else 400
        raise HTTPException(status_code=status, detail=error_message)

    response_body: dict = {"message": "User registered successfully"}

    # Start the 14-day no-card trial for parents/teachers immediately on signup.
    if body.role in ("teacher", "parent"):
        try:
            from services.billing.membership_service import MembershipService
            MembershipService().start_trial_if_eligible(body.username, body.role)
            response_body["trial_started"] = True
        except Exception as exc:  # pragma: no cover — billing is not auth-critical
            logger.warning("Trial creation failed for %s: %s", body.username, exc)

    if body.role == "student" and body.invite_code:
        invite_code = body.invite_code.strip().upper()
        try:
            _parent_service.accept_invite(body.username, invite_code)
            response_body["parent_linked"] = True
        except ValueError as inv_err:
            response_body["invite_warning"] = f"{inv_err}. You can link your parent account later from your profile."
        except Exception as inv_err:
            logger.warning("Failed to process invite code during signup: %s", inv_err)
            response_body["invite_warning"] = "Could not process invite code. You can link your parent account later from your profile."

    return response_body


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    username: str
    password: str
    role: str


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest):
    if not authenticate_user(body.username, body.password, body.role):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Lazy backfill: provision Supabase Auth entry for pre-Phase-1 users.
    try:
        backfill_supabase_auth_id(body.username, body.password, body.role)
    except Exception as exc:  # must not block login
        logger.warning("Supabase Auth backfill failed for %s: %s", body.username, exc)

    user = get_user_by_id(body.username)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    email: str = user["email"]

    try:
        sb_response = get_supabase_client().auth.sign_in_with_password(
            {"email": email, "password": body.password}
        )
    except Exception as exc:
        # Password may have drifted if a previous sync_password call failed silently.
        # authenticate_user() already verified body.password against bcrypt — it's correct.
        if user.get("supabase_auth_id"):
            try:
                SupabaseAuthService().sync_password(user["supabase_auth_id"], body.password)
                sb_response = get_supabase_client().auth.sign_in_with_password(
                    {"email": email, "password": body.password}
                )
            except Exception as retry_exc:
                logger.error("Supabase sign_in retry failed for %s: %s", body.username, retry_exc, exc_info=True)
                raise HTTPException(status_code=401, detail="Authentication failed")
        else:
            logger.error("Supabase sign_in_with_password failed for %s: %s", body.username, exc, exc_info=True)
            raise HTTPException(status_code=401, detail="Authentication failed")

    if not sb_response.session:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    response_data: dict = {
        "access_token": sb_response.session.access_token,
        "refresh_token": sb_response.session.refresh_token,
    }

    if body.role == "student":
        student = get_student_by_id(body.username)
        if student and (
            not student.get("strength")
            or not student.get("weakness")
            or not student.get("interest")
            or not student.get("learning_style")
        ):
            response_data["needs_profile"] = True

    # Backfill: legacy parent/teacher accounts created before the membership
    # system exist without a row. Auto-start their 14-day trial on first login
    # so they aren't suddenly blocked from creating/managing classes.
    if body.role in ("teacher", "parent"):
        try:
            from services.billing.membership_service import MembershipService
            MembershipService().start_trial_if_eligible(body.username, body.role)
        except Exception as exc:  # pragma: no cover — login must not depend on billing
            logger.warning("Trial backfill failed for %s on login: %s", body.username, exc)

    return response_data


# ---------------------------------------------------------------------------
# OAuth (Google / Apple / Microsoft via Supabase)
# ---------------------------------------------------------------------------

class OAuthCompleteRequest(BaseModel):
    access_token: str
    role: str
    grade: Optional[str] = None
    trial_confirmed: Optional[bool] = None


@router.post("/oauth/complete", response_model=OAuthCompleteResponse)
def oauth_complete(body: OAuthCompleteRequest):
    valid_roles = {"student", "teacher", "parent"}
    if body.role not in valid_roles:
        raise HTTPException(status_code=400, detail=f"Invalid role. Must be one of: {', '.join(valid_roles)}")

    result = _oauth_service.complete_oauth(
        access_token=body.access_token,
        role=body.role,
        grade=body.grade,
        trial_confirmed=body.trial_confirmed,
    )

    username: str = result["username"]

    if body.role in ("teacher", "parent"):
        try:
            from services.billing.membership_service import MembershipService
            MembershipService().start_trial_if_eligible(username, body.role)
        except Exception as exc:  # must not block login
            logger.warning("Trial backfill failed for OAuth user %s on login: %s", username, exc)

    # Session is established client-side via supabase.auth.exchangeCodeForSession in /auth/callback.
    return {"needs_profile": result.get("needs_profile", False)}


# ---------------------------------------------------------------------------
# Password reset
# ---------------------------------------------------------------------------

class PasswordResetRequestBody(BaseModel):
    email: str


class PasswordResetConfirmBody(BaseModel):
    token: str
    new_password: str


@router.post("/password-reset/request", response_model=PasswordResetRequestResponse)
async def password_reset_request(body: PasswordResetRequestBody, request: Request):
    if not body.email.strip():
        raise HTTPException(status_code=400, detail="Email is required")
    ip_address = get_client_ip(request)
    user_agent = request.headers.get("User-Agent", "")
    result = password_reset_service.request_password_reset(
        email=body.email.strip(),
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return {"message": result["message"]}


@router.post("/password-reset/confirm", response_model=PasswordResetConfirmResponse)
async def password_reset_confirm(body: PasswordResetConfirmBody, request: Request):
    if not body.token.strip():
        raise HTTPException(status_code=400, detail="Reset token is required")
    if not body.new_password:
        raise HTTPException(status_code=400, detail="New password is required")
    ip_address = get_client_ip(request)
    success, message = password_reset_service.confirm_password_reset(
        token=body.token.strip(),
        new_password=body.new_password,
        ip_address=ip_address,
    )
    if not success:
        raise HTTPException(status_code=400, detail=message)
    return {"message": message}
