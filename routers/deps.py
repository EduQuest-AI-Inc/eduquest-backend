import os
from enum import Enum
from typing import FrozenSet, Optional

import jwt
from fastapi import Cookie, Depends, Header, HTTPException, Request

JWT_SECRET = os.getenv("JWT_SECRET_KEY", "fallback-secret")
JWT_ALGORITHM = "HS256"


class Role(str, Enum):
    STUDENT = "student"
    TEACHER = "teacher"
    PARENT  = "parent"


class AuthPayload:
    def __init__(self, sub: str, role: Role, token: str) -> None:
        self.sub = sub        # decoded user id / teacher id
        self.role = role      # decoded role claim
        self.token = token    # raw JWT string — forwarded to SessionDAO-backed services


def get_auth(
    authorization: Optional[str] = Header(default=None),
    auth_token: Optional[str] = Cookie(default=None),
) -> AuthPayload:
    token: Optional[str] = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
    elif auth_token:
        token = auth_token

    if not token:
        raise HTTPException(status_code=401, detail="Missing auth token")

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return AuthPayload(
            sub=payload["sub"],
            role=Role(payload.get("role", Role.STUDENT)),
            token=token,
        )
    except (ValueError, KeyError):
        raise HTTPException(status_code=401, detail="Invalid token claims")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


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
