import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from responses.quest import (
    GradeQuestResponse,
    QuestOut,
    QuestStatusUpdateResponse,
    UpdateStepsResponse,
)
from routers.deps import AuthPayload, Role, get_auth
from services.enrollment.enrollment_service import EnrollmentService
from services.parent.parent_service import ParentService
from services.period.period_management_service import PeriodManagementService
from services.quest.quest_grading_service import QuestGradingService
from services.quest.quest_retrieval_service import QuestRetrievalService

logger = logging.getLogger(__name__)
router = APIRouter()
_retrieval_service = QuestRetrievalService()
_grading_service = QuestGradingService()
_enrollment_service = EnrollmentService()
_parent_service = ParentService()
_period_management_svc = PeriodManagementService()


@router.get("/quests", response_model=list[QuestOut])
def get_quests(
    period_id: Optional[str] = Query(default=None),
    auth: AuthPayload = Depends(get_auth),
):
    if period_id:
        quests = _retrieval_service.get_quests_for_student_and_period(auth.sub, period_id)
    else:
        quests = _retrieval_service.get_quests_for_student(auth.sub)
    for quest in quests:
        QuestRetrievalService.attach_grade_display(quest)
    return quests


@router.get("/quests/{quest_id}", response_model=QuestOut)
def get_quest(quest_id: str, auth: AuthPayload = Depends(get_auth)):
    quest = _retrieval_service.get_quest_by_id(quest_id)
    if quest:
        QuestRetrievalService.attach_grade_display(quest)
        return quest
    raise HTTPException(status_code=404, detail="Quest not found")


@router.get("/quests/student/{user_id}", response_model=list[QuestOut])
def get_student_quests(
    user_id: str,
    period_id: Optional[str] = Query(default=None),
    auth: AuthPayload = Depends(get_auth),
):
    """Teacher/parent route: fetch quests for a specific student."""
    if auth.sub != user_id:
        if auth.role == Role.PARENT:
            linked = _parent_service.get_linked_student_ids(auth.sub)
            if user_id not in linked:
                raise HTTPException(status_code=403, detail="Not authorized")
        else:
            enrollments = _enrollment_service.get_enrollments_by_student(user_id)
            period_ids = [e["period_id"] for e in enrollments]
            caller_periods = _period_management_svc.get_periods_by_owner(auth.sub)
            caller_period_ids = {p["period_id"] for p in caller_periods}
            if not any(pid in caller_period_ids for pid in period_ids):
                raise HTTPException(status_code=403, detail="Not authorized")
    if period_id:
        quests = _retrieval_service.get_quests_for_student_and_period(user_id, period_id)
    else:
        quests = _retrieval_service.get_quests_for_student(user_id)
    for quest in quests:
        QuestRetrievalService.attach_grade_display(quest)
    return quests


class UpdateStepsRequest(BaseModel):
    completed_steps: list[int]


@router.put("/quests/{quest_id}/steps", response_model=UpdateStepsResponse)
def update_quest_steps(
    quest_id: str,
    body: UpdateStepsRequest,
    auth: AuthPayload = Depends(get_auth),
):
    _grading_service.update_completed_steps(quest_id, body.completed_steps)
    return {"message": "Steps updated", "quest_id": quest_id, "completed_steps": body.completed_steps}


class UpdateQuestStatusRequest(BaseModel):
    status: str


@router.put("/quests/{quest_id}/status", response_model=QuestStatusUpdateResponse)
def update_quest_status(
    quest_id: str,
    body: UpdateQuestStatusRequest,
    auth: AuthPayload = Depends(get_auth),
):
    if body.status not in ("not_started", "in_progress", "completed"):
        raise HTTPException(status_code=400, detail="status must be one of: not_started, in_progress, completed")
    return _grading_service.update_quest_status(quest_id, body.status)


class GradeQuestRequest(BaseModel):
    grade: dict
    feedback: str


@router.put("/quests/{quest_id}/grade", response_model=GradeQuestResponse)
def grade_quest(
    quest_id: str,
    body: GradeQuestRequest,
    auth: AuthPayload = Depends(get_auth),
):
    _grading_service.update_quest_grade_and_feedback(quest_id, body.grade, body.feedback)
    return {"message": "Grade and feedback submitted successfully", "quest_id": quest_id}


@router.get("/verify-quest-structure/{period_id}", response_model=dict[str, Any])
def verify_quest_structure(period_id: str, auth: AuthPayload = Depends(get_auth)):
    return _retrieval_service.verify_quest_structure(auth.sub, period_id)
