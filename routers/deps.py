import os
from datetime import datetime, timezone
from enum import Enum
from typing import FrozenSet, Optional

import jwt
from jwt import PyJWKClient
from fastapi import Cookie, Depends, Header, HTTPException, Path, Request

from data_access.student_dao import StudentDAO

# Dead code until Phase 6 — kept to avoid breaking any callers during rollout.
JWT_SECRET = os.getenv("JWT_SECRET_KEY", "fallback-secret")
JWT_ALGORITHM = "HS256"

SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "")
SUPABASE_URL = os.getenv("SUPABASE_URL", "")

_jwks_client: Optional[PyJWKClient] = None


def _get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = PyJWKClient(f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json")
    return _jwks_client


class Role(str, Enum):
    STUDENT = "student"
    TEACHER = "teacher"
    PARENT  = "parent"


class AuthPayload:
    def __init__(self, sub: str, role: Role, token: str) -> None:
        self.sub = sub        # decoded user id / teacher id
        self.role = role      # decoded role claim
        self.token = token    # raw JWT string — forwarded to SessionDAO-backed services


def _enforce_student_compliance(
    username: str,
    role: Role,
    compliance_status: Optional[str] = None,
    compliance_review_due_at: Optional[str] = None,
    student_dao=None,
) -> None:
    if role != Role.STUDENT:
        return

    if compliance_status is None:
        # Fallback: claim absent (session predates this feature or first login before token refresh).
        dao = student_dao or StudentDAO()
        student = dao.get_student_by_id(username)
        if not student:
            raise HTTPException(status_code=403, detail="Student compliance record is missing.")
        compliance_status = student.get("compliance_status")
        compliance_review_due_at = student.get("compliance_review_due_at")

    if compliance_status == "legacy_review_due":
        due_raw = compliance_review_due_at
        if due_raw:
            due = datetime.fromisoformat(due_raw.replace("Z", "+00:00"))
            if due.tzinfo is None:
                due = due.replace(tzinfo=timezone.utc)
            if due > datetime.now(timezone.utc):
                return
    if compliance_status != "active":
        raise HTTPException(
            status_code=403,
            detail={
                "error": "Student authorization required",
                "code": "STUDENT_COMPLIANCE_REVIEW_REQUIRED",
            },
        )


def get_auth(
    authorization: Optional[str] = Header(default=None),
    auth_token: Optional[str] = Cookie(default=None),
) -> AuthPayload:
    if not SUPABASE_URL:
        raise RuntimeError("SUPABASE_URL must be set")

    token: Optional[str] = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
    elif auth_token:
        token = auth_token

    if not token:
        raise HTTPException(status_code=401, detail="Missing auth token")

    try:
        header = jwt.get_unverified_header(token)
        alg = header.get("alg", "HS256")
        if alg == "HS256":
            payload = jwt.decode(
                token,
                SUPABASE_JWT_SECRET,
                algorithms=["HS256"],
                audience="authenticated",
            )
        else:
            signing_key = _get_jwks_client().get_signing_key_from_jwt(token)
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=["ES256", "RS256"],
                audience="authenticated",
            )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidAudienceError:
        # Pre-migration HS256 tokens lack audience="authenticated" — tell the user to re-login
        raise HTTPException(
            status_code=401,
            detail="Session format outdated — please log out and log back in",
        )
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

    app_meta = payload.get("app_metadata") or {}
    username = app_meta.get("username")
    role_str = app_meta.get("role")

    if not username or not role_str:
        raise HTTPException(
            status_code=401,
            detail="User not provisioned in Supabase Auth — run Phase 1 migration",
        )

    try:
        role = Role(role_str)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid token claims")

    _enforce_student_compliance(
        username,
        role,
        compliance_status=app_meta.get("compliance_status"),
        compliance_review_due_at=app_meta.get("compliance_review_due_at"),
    )
    return AuthPayload(sub=username, role=role, token=token)


def require_roles(*roles: Role):
    """
    Dependency factory. Restricts a route to callers with one of the given roles.

    Usage:
        auth: AuthPayload = Depends(require_roles(Role.TEACHER))
        auth: AuthPayload = Depends(require_roles(Role.TEACHER, Role.PARENT))
    """
    allowed: FrozenSet[Role] = frozenset(roles)

    def _check(auth: AuthPayload = Depends(get_auth)) -> AuthPayload:
        if auth.role not in allowed:
            raise HTTPException(
                status_code=403,
                detail=f"Requires one of: {[r.value for r in allowed]}",
            )
        return auth

    return _check


def require_active_membership(auth: AuthPayload = Depends(get_auth)) -> AuthPayload:
    """
    FastAPI dependency. Restricts a route to parent/teacher callers whose
    membership is currently active (trialing or paid). Students are never
    affected by this gate; they reach it only via mis-routing, in which case
    we fail closed with code `OWNER_ROLE_REQUIRED`.

    Returns a structured 403 with code `MEMBERSHIP_REQUIRED` so the frontend
    can render the paywall UI.

    Usage:
        auth: AuthPayload = Depends(require_active_membership)
    """
    if auth.role not in (Role.TEACHER, Role.PARENT):
        raise HTTPException(
            status_code=403,
            detail={"error": "Forbidden", "code": "OWNER_ROLE_REQUIRED"},
        )
    # Lazy import to avoid circulars between routers and services.
    from services.billing.membership_service import MembershipService
    access = MembershipService().evaluate_access(auth.sub, auth.role.value)
    if not access.has_active_membership:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "Active membership required",
                "code": "MEMBERSHIP_REQUIRED",
                "status": access.status.value,
                "trial_ends_at": access.trial_ends_at,
            },
        )
    return auth


def get_bot_provider(request: Request):
    """FastAPI dependency — reads the provider initialised in main.py lifespan."""
    from bots.protocol import BotProviderProtocol  # noqa: F401
    return request.app.state.bot_provider


def get_period_file_service(
    bot_provider=Depends(get_bot_provider),
    auth: AuthPayload = Depends(get_auth),
):
    """FastAPI dependency — wires PeriodFileService with all orchestration deps."""
    from services.period.period_file_service import PeriodFileService
    from services.period.period_management_service import PeriodManagementService
    from services.curriculum.curriculum_service import CurriculumService
    return PeriodFileService(
        bot_provider=bot_provider,
        period_management_service=PeriodManagementService(jwt=auth.token),
        curriculum_service=CurriculumService(bot_provider=bot_provider, jwt=auth.token),
    )


def get_period(period_id: str = Path(...)) -> dict:
    from services.period.period_management_service import PeriodManagementService
    period = PeriodManagementService().get_period_by_id(period_id)
    if not period:
        raise HTTPException(status_code=404, detail=f"Period '{period_id}' not found")
    return period


def require_student_viewer(student_id_param: str = "user_id"):
    """
    Dependency factory for routes where a teacher or parent may optionally provide
    a student user_id to view that student's data. If no student_id is given,
    the caller is accessing their own data and passes through.

    Usage:
        auth: AuthPayload = Depends(require_student_viewer("user_id"))
    """
    from fastapi import Request
    from services.enrollment.enrollment_service import EnrollmentService
    from services.parent.parent_service import ParentService

    _parent_svc = ParentService()
    _enrollment_svc = EnrollmentService()

    def _check(request: Request, auth: AuthPayload = Depends(get_auth)) -> AuthPayload:
        student_id = (
            request.query_params.get(student_id_param)
            or request.path_params.get(student_id_param)
        )
        if not student_id:
            return auth  # accessing own data

        if auth.role == Role.PARENT:
            linked = _parent_svc.get_linked_student_ids(auth.sub)
            if student_id not in linked:
                raise HTTPException(status_code=403, detail="Access denied")
        elif auth.role == Role.TEACHER:
            if not _enrollment_svc.has_teacher_access_to_student(auth.sub, student_id):
                raise HTTPException(status_code=403, detail="Access denied")
        else:
            raise HTTPException(status_code=403, detail="Access denied")

        return auth

    return _check
