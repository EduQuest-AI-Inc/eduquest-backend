"""Self-directed course creation — creates a student-owned period with curriculum generation."""
import logging
import re
import uuid
from datetime import datetime, timezone

from fastapi import BackgroundTasks

from bots.protocol import BotProviderProtocol
from data_access.enrollment_dao import EnrollmentDAO
from data_access.period_dao import PeriodDAO
from exceptions.permission_error import PermissionError
from models.enrollment import Enrollment
from models.period import Period

logger = logging.getLogger(__name__)


def check_period_access(user_id: str, period: dict) -> None:
    """Raise PermissionError if user cannot access this period.

    Self-directed periods are owned by the student themselves; all other periods
    require teacher/parent ownership.
    """
    if period.get("course_mode") == "self_directed":
        if period.get("owner_id") != user_id:
            raise PermissionError("Not your course")
    else:
        if period.get("owner_id") != user_id:
            raise PermissionError("Access denied")


class AdaptiveCourseService:
    def __init__(
        self,
        *,
        bot_provider: BotProviderProtocol,
        period_dao=None,
        enrollment_dao=None,
    ) -> None:
        self._bot_provider = bot_provider
        # Admin client — student JWT cannot create periods (RLS blocks cross-user inserts)
        self._period_dao = period_dao or PeriodDAO()
        self._enrollment_dao = enrollment_dao or EnrollmentDAO()

    def create_course(
        self,
        *,
        student_id: str,
        name: str,
        description: str = "",
        background_tasks: BackgroundTasks,
    ) -> str:
        """Create a self-directed period, enroll the student, and queue curriculum generation.

        Membership/capacity guards are intentionally skipped for v1 self-directed courses.
        Returns period_id.
        """
        period_id = self._generate_period_id(name)

        period = Period(
            period_id=period_id,
            name=name,
            owner_id=student_id,
            course_description=description or None,
            course_mode="self_directed",
            owner_role="student",
            status="pending",
        )
        self._period_dao.add_period(period)

        enrollment = Enrollment(
            user_id=student_id,
            period_id=period_id,
            semester="Self-Directed",
            enrolled_at=datetime.now(timezone.utc).isoformat(),
        )
        self._enrollment_dao.add_enrollment(enrollment)

        background_tasks.add_task(self._run_curriculum, period_id)
        logger.info("adaptive course created: period_id=%s owner=%s", period_id, student_id)
        return period_id

    def _run_curriculum(self, period_id: str) -> None:
        from services.adaptive.skill_resolver import SkillResolver
        from services.curriculum.curriculum_service import CurriculumService

        svc = CurriculumService(
            bot_provider=self._bot_provider,
            skill_resolver=SkillResolver(),
        )
        if not self._period_dao.try_start_generating(period_id):
            logger.warning("adaptive curriculum already generating: period_id=%s", period_id)
            return
        try:
            svc.run_generation(period_id)
        except Exception:
            logger.exception("adaptive curriculum generation failed: period_id=%s", period_id)

    @staticmethod
    def _generate_period_id(name: str) -> str:
        clean = re.sub(r"[^a-zA-Z0-9]", "", name).upper()[:8]
        r1 = str(uuid.uuid4())[:4].upper()
        r2 = str(uuid.uuid4())[:4].upper()
        return f"SD-{clean}-{r1}-{r2}"
