import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from routers.deps import AuthPayload, get_auth, require_student_viewer
from responses.user import TutorialStatusResponse, UpdateTutorialResponse, UserProfileResponse
from services.user.user_service import UserService

logger = logging.getLogger(__name__)
router = APIRouter()


def _fetch_user_profile(user_id: str, jwt: str) -> Optional[dict]:
    svc = UserService(jwt=jwt)
    user = svc.get_by_id(user_id)
    if not user:
        return None
    role = user.get("role") or ""
    role_fetchers = {
        "student": lambda uid: svc.get_student_by_id(uid),
        "teacher": lambda uid: svc.get_teacher_by_id(uid),
        "parent":  lambda uid: svc.get_parent_by_id(uid),
    }
    fetcher = role_fetchers.get(role)
    if not fetcher:
        return None
    profile = fetcher(user_id)
    if not profile:
        return None
    profile["role"] = role
    if role == "teacher":
        profile.setdefault("pilot_approved", False)
        profile.pop("canvas_api_key", None)
    if role in ("teacher", "parent"):
        try:
            from services.billing.membership_service import MembershipService
            access = MembershipService(jwt=jwt).evaluate_access(user_id, role)
            profile["membership"] = {
                "status": access.status.value,
                "plan": access.plan.value if access.plan else None,
                "has_active_membership": access.has_active_membership,
                "trial_ends_at": access.trial_ends_at,
                "class_limit": access.class_limit,
                "students_per_class_limit": access.students_per_class_limit,
            }
        except Exception:
            profile["membership"] = {
                "status": "none",
                "plan": None,
                "has_active_membership": False,
                "trial_ends_at": None,
                "class_limit": None,
                "students_per_class_limit": None,
            }
    return profile


@router.get("/profile", response_model=UserProfileResponse)
def get_profile(
    user_id: Optional[str] = None,
    auth: AuthPayload = Depends(require_student_viewer("user_id")),
):
    profile = _fetch_user_profile(user_id or auth.sub, auth.token)
    if not profile:
        raise HTTPException(status_code=404, detail="User not found")
    return profile


class UpdateTutorialRequest(BaseModel):
    completed_tutorial: bool = False


@router.post("/update-tutorial", response_model=UpdateTutorialResponse)
def update_tutorial(body: UpdateTutorialRequest, auth: AuthPayload = Depends(get_auth)):
    svc = UserService(jwt=auth.token)
    svc.update_tutorial_status(auth.sub, body.completed_tutorial)
    return {"message": "Tutorial status updated successfully"}


@router.get("/tutorial-status", response_model=TutorialStatusResponse)
def get_tutorial_status(auth: AuthPayload = Depends(get_auth)):
    svc = UserService(jwt=auth.token)
    status = svc.get_tutorial_status(auth.sub)
    return {"completed_tutorial": status}
