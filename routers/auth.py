import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from constants.timeouts import JWT_EXPIRY_HOURS
from responses.auth import (
    AgeScreenResponse,
    DeleteAccountResponse,
    LoginResponse,
    OAuthCompleteResponse,
    PasswordResetConfirmResponse,
    PasswordResetRequestResponse,
    SignupResponse,
    StudentEmailConfirmResponse,
    StudentEmailRequestResponse,
)
from routers.deps import AuthPayload, require_roles, Role
from services.auth.account_deletion_service import AccountDeletionService
from services.auth.age_screen_service import AGE_SCREEN_COOKIE, AgeScreenService
from services.billing.membership_service import MembershipService
from services.auth.student_email_verification_service import (
    STUDENT_EMAIL_COOKIE,
    StudentEmailVerificationService,
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
from services.tracking import Events, track_event
from utils.validation_utils import get_client_ip

logger = logging.getLogger(__name__)
router = APIRouter()

# Dead code until Phase 6 — kept to avoid breaking any external callers during rollout.
JWT_SECRET = os.getenv("JWT_SECRET_KEY", "fallback-secret")
JWT_ALGORITHM = "HS256"

_parent_service = ParentService()
_oauth_service = OAuthService()
_supabase_auth_service = SupabaseAuthService()
password_reset_service = get_password_reset_service()


def _get_age_screen_service() -> AgeScreenService:
    return AgeScreenService()


def _get_student_email_verification_service() -> StudentEmailVerificationService:
    return StudentEmailVerificationService()


def _require_first_party_origin(request: Request) -> None:
    origin = request.headers.get("origin", "").rstrip("/")
    configured = (os.getenv("FRONTEND_BASE_URL") or "").rstrip("/")
    allowed = {
        configured,
        "https://eduquestai.org",
        "https://www.eduquestai.org",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    }
    allowed.discard("")
    if origin not in allowed:
        raise HTTPException(status_code=403, detail="Age screening must start from the EduQuest website.")


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
    age_band: Optional[str] = None
    adult_attestation: Optional[bool] = None
    # Required confirmation for parent/teacher accounts: explicit acknowledgement
    # that they are starting the 14-day no-card trial. The frontend renders the
    # trial-terms screen and only sets this to True after the user confirms.
    trial_confirmed: Optional[bool] = None


class AgeScreenRequest(BaseModel):
    birth_month: int
    birth_year: int


class StudentEmailVerificationRequest(BaseModel):
    email: str


class StudentEmailVerificationConfirmRequest(BaseModel):
    email: str
    code: str


@router.post("/age-screen", response_model=AgeScreenResponse)
def age_screen(body: AgeScreenRequest, request: Request, response: Response):
    _require_first_party_origin(request)
    raw_token, age_band = _get_age_screen_service().create(
        birth_month=body.birth_month,
        birth_year=body.birth_year,
        request_ip=get_client_ip(request),
    )
    response.set_cookie(
        AGE_SCREEN_COOKIE,
        raw_token,
        httponly=True,
        secure=os.getenv("APP_ENV", "production") != "development",
        samesite="strict",
        max_age=10 * 60,
        path="/api/auth",
    )
    return {
        "age_band": age_band,
        "next_step": "adult_signup" if age_band == "18_plus" else "parent_authorization",
    }


@router.post("/student-email/request", response_model=StudentEmailRequestResponse)
def request_student_email_verification(body: StudentEmailVerificationRequest, request: Request):
    _require_first_party_origin(request)
    _get_student_email_verification_service().request_code(
        email=body.email,
        age_screen_token=request.cookies.get(AGE_SCREEN_COOKIE),
        request_ip=get_client_ip(request),
    )
    return {"message": "If the address is valid, a verification code has been sent."}


@router.post("/student-email/confirm", response_model=StudentEmailConfirmResponse)
def confirm_student_email_verification(
    body: StudentEmailVerificationConfirmRequest,
    request: Request,
    response: Response,
):
    _require_first_party_origin(request)
    raw_token = _get_student_email_verification_service().confirm_code(
        email=body.email,
        code=body.code,
        request_ip=get_client_ip(request),
    )
    response.set_cookie(
        STUDENT_EMAIL_COOKIE,
        raw_token,
        httponly=True,
        secure=os.getenv("APP_ENV", "production") != "development",
        samesite="strict",
        max_age=10 * 60,
        path="/api/auth",
    )
    return {"message": "Email verified."}


@router.post("/signup", status_code=201, response_model=SignupResponse)
def signup(body: SignupRequest, request: Request):
    valid_roles = {"student", "teacher", "parent"}
    if body.role not in valid_roles:
        raise HTTPException(status_code=400, detail=f"Invalid role. Must be one of: {', '.join(valid_roles)}")
    if body.role == "student" and not body.grade:
        raise HTTPException(status_code=400, detail="grade is required for students")
    normalized_email = body.email.strip().lower()
    if get_user_by_email(normalized_email):
        raise HTTPException(status_code=409, detail="Email address already in use")
    if body.role == "student":
        if body.age_band not in {"under_13", "13_to_17", "18_plus"}:
            raise HTTPException(status_code=400, detail="age_band is required for students")
        _get_age_screen_service().consume(
            request.cookies.get(AGE_SCREEN_COOKIE),
            expected_band=body.age_band,
        )
        if body.age_band != "18_plus":
            raise HTTPException(
                status_code=403,
                detail="A parent or guardian must authorize a minor student account before signup.",
            )
        if body.adult_attestation is not True:
            raise HTTPException(
                status_code=400,
                detail="Adult students must attest that they are at least 18 years old.",
            )
        _get_student_email_verification_service().consume(
            email=normalized_email,
            raw_token=request.cookies.get(STUDENT_EMAIL_COOKIE),
        )
    if body.role in ("teacher", "parent") and not body.trial_confirmed:
        raise HTTPException(
            status_code=400,
            detail="trial_confirmed is required for parent/teacher signups",
        )

    result = register_user(
        body.username, body.password, body.role,
        body.first_name, body.last_name, normalized_email,
        body.grade if body.role == "student" else None,
        body.phone_number,
        body.age_band if body.role == "student" else None,
    )
    if not result.get("success"):
        error_message = result.get("error", "Registration failed")
        status = 409 if "already exists" in error_message else 400
        track_event(
            user_id="signup_unknown",
            event=Events.USER_SIGNUP_FAILED,
            properties={
                "failure_reason": "email_taken" if status == 409 else "server_error",
                "role": body.role,
            },
        )
        raise HTTPException(status_code=status, detail=error_message)

    response_body: dict = {"message": "User registered successfully"}

    # Start the 14-day no-card trial for parents/teachers immediately on signup.
    if body.role in ("teacher", "parent"):
        try:
            MembershipService().start_trial_if_eligible(body.username, body.role)
            response_body["trial_started"] = True
        except Exception as exc:  # pragma: no cover — billing is not auth-critical
            logger.warning("Trial creation failed for %s: %s", body.username, exc)
            track_event(
                user_id=body.username,
                event=Events.MEMBERSHIP_TRIAL_CREATION_FAILED,
                properties={"trigger": "signup", "role": body.role, "error_type": type(exc).__name__},
            )

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
        track_event(
            user_id="login_unknown",
            event=Events.USER_LOGIN_FAILED,
            properties={"failure_reason": "bad_credentials", "role": body.role},
        )
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Lazy backfill: provision Supabase Auth entry for pre-Phase-1 users.
    try:
        backfill_supabase_auth_id(body.username, body.password, body.role)
    except Exception as exc:  # must not block login
        logger.warning("Supabase Auth backfill failed for %s: %s", body.username, exc)

    user = get_user_by_id(body.username)
    if not user:
        track_event(
            user_id="login_unknown",
            event=Events.USER_LOGIN_FAILED,
            properties={"failure_reason": "bad_credentials", "role": body.role},
        )
        raise HTTPException(status_code=401, detail="Invalid credentials")

    email: str = user["email"]

    try:
        sb_response = _supabase_auth_service.sign_in_with_password(email, body.password)
    except Exception as exc:
        # Password may have drifted if a previous sync_password call failed silently.
        # authenticate_user() already verified body.password against bcrypt — it's correct.
        if user.get("supabase_auth_id"):
            try:
                _supabase_auth_service.sync_password(user["supabase_auth_id"], body.password)
                sb_response = _supabase_auth_service.sign_in_with_password(email, body.password)
            except Exception as retry_exc:
                logger.error("Supabase sign_in retry failed for %s: %s", body.username, retry_exc, exc_info=True)
                track_event(
                    user_id="login_unknown",
                    event=Events.USER_LOGIN_FAILED,
                    properties={"failure_reason": "server_error", "role": body.role,
                                "error_type": type(retry_exc).__name__},
                )
                raise HTTPException(status_code=401, detail="Authentication failed")
        else:
            logger.error("Supabase sign_in_with_password failed for %s: %s", body.username, exc, exc_info=True)
            track_event(
                user_id="login_unknown",
                event=Events.USER_LOGIN_FAILED,
                properties={"failure_reason": "server_error", "role": body.role,
                            "error_type": type(exc).__name__},
            )
            raise HTTPException(status_code=401, detail="Authentication failed")

    if not sb_response.session:
        track_event(
            user_id="login_unknown",
            event=Events.USER_LOGIN_FAILED,
            properties={"failure_reason": "server_error", "role": body.role},
        )
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
        # Sync compliance into Supabase app_metadata so the next JWT refresh carries
        # the claim and deps.py can skip the per-request DB call.
        if student and sb_response.session.user:
            try:
                _supabase_auth_service.sync_compliance_to_app_metadata(
                    sb_response.session.user.id,
                    student.get("compliance_status", "blocked"),
                    student.get("compliance_review_due_at"),
                )
            except Exception as exc:
                logger.warning("Compliance app_metadata sync failed for %s: %s", body.username, exc)

    # Backfill: legacy parent/teacher accounts created before the membership
    # system exist without a row. Auto-start their 14-day trial on first login
    # so they aren't suddenly blocked from creating/managing classes.
    if body.role in ("teacher", "parent"):
        try:
            MembershipService().start_trial_if_eligible(body.username, body.role)
        except Exception as exc:  # pragma: no cover — login must not depend on billing
            logger.warning("Trial backfill failed for %s on login: %s", body.username, exc)
            track_event(
                user_id=body.username,
                event=Events.MEMBERSHIP_TRIAL_CREATION_FAILED,
                properties={"trigger": "login", "role": body.role, "error_type": type(exc).__name__},
            )

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
            MembershipService().start_trial_if_eligible(username, body.role)
        except Exception as exc:  # must not block login
            logger.warning("Trial backfill failed for OAuth user %s on login: %s", username, exc)
            track_event(
                user_id=username,
                event=Events.MEMBERSHIP_TRIAL_CREATION_FAILED,
                properties={"trigger": "oauth_login", "role": body.role, "error_type": type(exc).__name__},
            )

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


@router.delete("/account", status_code=200, response_model=DeleteAccountResponse)
def delete_account(auth: AuthPayload = Depends(require_roles(Role.STUDENT, Role.TEACHER, Role.PARENT))):
    AccountDeletionService().delete_account(auth.sub, auth.role.value)
    return {"message": "Account deleted successfully."}


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
