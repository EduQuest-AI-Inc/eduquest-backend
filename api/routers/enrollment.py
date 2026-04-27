import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.deps import AuthPayload, get_auth
from data_access.period_dao import PeriodDAO
from services.enrollment.enrollment_service import EnrollmentService

logger = logging.getLogger(__name__)
router = APIRouter()
service = EnrollmentService()
_period_dao = PeriodDAO()


class EnrollRequest(BaseModel):
    period_id: str
    semester: str = "Fall 2025"


@router.post("/enroll")
def enroll(body: EnrollRequest, auth: AuthPayload = Depends(get_auth)):
    try:
        result = service.enroll_student(auth.sub, body.period_id, body.semester)
        return result
    except Exception as e:
        logger.error("Enrollment error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Server error")


@router.get("/enrollments/{period_id}")
def get_enrollments(period_id: str, auth: AuthPayload = Depends(get_auth)):
    period = _period_dao.get_period_by_id(period_id)
    if not period:
        raise HTTPException(status_code=404, detail="Period not found")
    if period.get("owner_id") != auth.sub:
        raise HTTPException(status_code=403, detail="Not authorized")
    try:
        enrollments = service.get_enrollments_for_period(period_id)
        return enrollments
    except Exception as e:
        logger.error("Error fetching enrollments: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch enrollments")


@router.get("/student-profile/{period_id}/{user_id}")
def get_student_profile(period_id: str, user_id: str, auth: AuthPayload = Depends(get_auth)):
    period = _period_dao.get_period_by_id(period_id)
    if not period:
        raise HTTPException(status_code=404, detail="Period not found")
    if period.get("owner_id") != auth.sub:
        raise HTTPException(status_code=403, detail="Not authorized")
    try:
        profile = service.get_student_profile(period_id, user_id)
        if profile:
            return profile
        raise HTTPException(status_code=404, detail="Profile not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error fetching student profile: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Server error")
