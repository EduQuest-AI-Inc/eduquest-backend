import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from constants.timeouts import JWT_EXPIRY_HOURS
from models.session import Session
from services.auth.auth_service import (
    add_session,
    authenticate_user,
    get_student_by_id,
    get_user_by_email,
    register_user,
)
from services.parent.parent_service import ParentService
from services.auth.password_reset_service import get_password_reset_service
from utils.token_utils import set_auth_cookie
from utils.validation_utils import get_client_ip

logger = logging.getLogger(__name__)
router = APIRouter()

JWT_SECRET = os.getenv("JWT_SECRET_KEY", "fallback-secret")
JWT_ALGORITHM = "HS256"

_parent_service = ParentService()
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


@router.post("/signup", status_code=201)
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
        except Exception as e:  # pragma: no cover — billing is not auth-critical
            logger.warning("Trial creation failed for %s: %s", body.username, e)

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


@router.post("/login")
def login(body: LoginRequest, response: Response):
    if not authenticate_user(body.username, body.password, body.role):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = _mint_token(body.username, body.role)
    session = Session(auth_token=token, user_id=body.username, role=body.role)  # type: ignore[arg-type]
    add_session(session)

    response_data: dict = {"token": token}
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
        except Exception as e:  # pragma: no cover — login must not depend on billing
            logger.warning("Trial backfill failed for %s on login: %s", body.username, e)

    set_auth_cookie(response, token)
    return response_data


# ---------------------------------------------------------------------------
# Password reset
# ---------------------------------------------------------------------------

class PasswordResetRequestBody(BaseModel):
    email: str


class PasswordResetConfirmBody(BaseModel):
    token: str
    new_password: str


@router.post("/password-reset/request")
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


@router.post("/password-reset/confirm")
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
