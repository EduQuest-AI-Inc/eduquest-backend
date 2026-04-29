import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from api.deps import AuthPayload, get_auth
from data_access.enrollment_dao import EnrollmentDAO
from data_access.period_dao import PeriodDAO
from data_access.quest_dao import QuestDAO
from services.quest.quest_retrieval_service import QuestRetrievalService
from services.quest.quest_service import QuestService

logger = logging.getLogger(__name__)
router = APIRouter()
quest_service = QuestService()
quest_dao = QuestDAO()
enrollment_dao = EnrollmentDAO()
period_dao = PeriodDAO()


@router.get("/quests")
def get_quests(
    period_id: Optional[str] = Query(default=None),
    auth: AuthPayload = Depends(get_auth),
):
    try:
        if period_id:
            quests = quest_service.get_quests_for_student_and_period(auth.sub, period_id)
        else:
            quests = quest_service.get_quests_for_student(auth.sub)
        for quest in quests:
            QuestRetrievalService.attach_grade_display(quest)
        return quests
    except Exception as e:
        logger.error("Error getting quests: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get quests")


@router.get("/quests/{quest_id}")
def get_quest(quest_id: str, auth: AuthPayload = Depends(get_auth)):
    try:
        quest = quest_dao.get_quest_by_id(quest_id)
        if quest:
            QuestRetrievalService.attach_grade_display(quest)
            return quest
        raise HTTPException(status_code=404, detail="Quest not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error getting quest: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get quest")


@router.get("/quests/student/{user_id}")
def get_student_quests(user_id: str, auth: AuthPayload = Depends(get_auth)):
    """Teacher/parent route: fetch quests for a specific student."""
    if auth.sub != user_id:
        enrollments = enrollment_dao.get_enrollments_by_student(user_id)
        period_ids = [e["period_id"] for e in enrollments]
        caller_periods = period_dao.get_periods_by_owner_id(auth.sub)
        caller_period_ids = {p["period_id"] for p in caller_periods}
        if not any(pid in caller_period_ids for pid in period_ids):
            raise HTTPException(status_code=403, detail="Not authorized")
    try:
        quests = quest_service.get_quests_for_student(user_id)
        for quest in quests:
            QuestRetrievalService.attach_grade_display(quest)
        return quests
    except Exception as e:
        logger.error("Error getting student quests: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get student quests")


class UpdateQuestStatusRequest(BaseModel):
    status: str


@router.put("/quests/{quest_id}/status")
def update_quest_status(
    quest_id: str,
    body: UpdateQuestStatusRequest,
    auth: AuthPayload = Depends(get_auth),
):
    if body.status not in ("not_started", "in_progress", "completed"):
        raise HTTPException(status_code=400, detail="status must be one of: not_started, in_progress, completed")
    try:
        result = quest_service.update_quest_status(quest_id, body.status)
        return result
    except Exception as e:
        logger.error("Error updating quest status: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update quest status")


class GradeQuestRequest(BaseModel):
    grade: str
    feedback: str


@router.put("/quests/{quest_id}/grade")
def grade_quest(
    quest_id: str,
    body: GradeQuestRequest,
    auth: AuthPayload = Depends(get_auth),
):
    try:
        quest_dao.update_quest_grade_and_feedback(quest_id, body.grade, body.feedback)
        return {"message": "Grade and feedback submitted successfully", "quest_id": quest_id}
    except Exception as e:
        logger.error("Error grading quest: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to grade quest")


class ParseGradeRequest(BaseModel):
    grade: object


@router.post("/grade/parse")
def parse_grade_data(body: ParseGradeRequest):
    try:
        grade_info = quest_service.parse_grade_data(body.grade)
        return {"parsed_grade": grade_info, "display_grade": grade_info["display_grade"]}
    except Exception as e:
        logger.error("Error parsing grade data: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to parse grade data")


@router.get("/verify-quest-structure/{period_id}")
def verify_quest_structure(period_id: str, auth: AuthPayload = Depends(get_auth)):
    try:
        verification = quest_service.verify_quest_structure(auth.sub, period_id)
        return verification
    except Exception as e:
        logger.error("Error verifying quest structure: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to verify quest structure")
