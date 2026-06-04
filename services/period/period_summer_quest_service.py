import logging
from typing import Any

from bots.protocol import BotProviderProtocol
from data_access.period_dao import PeriodDAO
from data_access.student_long_term_goal_dao import StudentLongTermGoalDAO
from exceptions.not_found_error import NotFoundError
from exceptions.permission_error import PermissionError
from exceptions.validation_error import ValidationError
from services.curriculum.curriculum_service import CurriculumService
from services.quest.quest_grading_service import QuestGradingService
from services.tracking import Events, track_event

logger = logging.getLogger(__name__)



def _build_schedule(curriculum: dict[str, Any]) -> list[dict[str, Any]]:
    """Assemble the [{Week, Skills}] list the CurriculumOnlyQuestAgent expects."""
    weeks = curriculum.get("weeks", [])
    all_lessons = curriculum.get("lessons", [])
    all_concepts = curriculum.get("concepts", [])

    lesson_to_week = {
        lesson.get("lesson_name"): lesson.get("week_number")
        for lesson in all_lessons
    }
    concepts_by_week: dict[int, list[str]] = {}
    for concept in all_concepts:
        week_num = lesson_to_week.get(concept.get("lesson_name"))
        if week_num is not None:
            concepts_by_week.setdefault(week_num, []).append(concept.get("concept_name", ""))

    schedule = []
    for week in weeks:
        week_num = week.get("week_number")
        concepts = concepts_by_week.get(week_num, [])
        skills = "; ".join(concepts) if concepts else "Practice skills from this week"
        schedule.append({"Week": week_num, "Skills": skills})
    return schedule


class PeriodSummerQuestService:
    """
    Orchestrates summer quest generation for a side-quest period.

    Flow: fetch curriculum → build schedule → run CurriculumOnlyQuestAgent →
          persist long-term goal → persist quests.

    The period owner is also enrolled as a student (auto-enrolled on period creation),
    so their user_id is used as the student_id for all quest and goal records.
    """

    def __init__(self, *, bot_provider: BotProviderProtocol) -> None:
        self._bot_provider = bot_provider
        self.period_dao = PeriodDAO()
        self.curriculum_service = CurriculumService(bot_provider=bot_provider)
        self.ltg_goal_dao = StudentLongTermGoalDAO()
        self.quest_service = QuestGradingService()

    def generate_summer_quests(self, owner_id: str, period_id: str) -> dict[str, Any]:
        period = self.period_dao.get_period_by_id(period_id)
        if not period:
            raise NotFoundError("Period not found")
        if period.get("owner_id") != owner_id:
            raise PermissionError("Only the period owner can generate summer quests")
        if not period.get("is_summer_quest"):
            raise ValidationError("This endpoint is only for summer side quests")

        curriculum = self.curriculum_service.get_curriculum(period_id)
        if curriculum.get("period_status") != "approved":
            raise ValidationError(
                "Curriculum must be approved before generating quests. "
                "Use the 'Confirm Quests' button first."
            )

        weeks = curriculum.get("weeks", [])
        if not weeks:
            raise NotFoundError(
                "No curriculum weeks found. Generate and approve a curriculum first."
            )

        schedule = _build_schedule(curriculum)
        if not schedule:
            raise ValidationError("No quests could be built from the approved curriculum.")

        logger.info(
            "PeriodSummerQuestService: starting generation for period %s — %d weeks",
            period_id,
            len(schedule),
        )

        agent = self._bot_provider.create_curriculum_only_quest_agent(
            period=period, schedule=schedule
        )
        goal_text, quests = agent.run()

        logger.info(
            "PeriodSummerQuestService: agent finished — goal=%r, %d quests",
            goal_text[:60],
            len(quests),
        )

        self.ltg_goal_dao.upsert(owner_id, period_id, goal_text)
        logger.info(
            "PeriodSummerQuestService: long-term goal persisted for user %s period %s",
            owner_id,
            period_id,
        )

        homework_data = {
            "list_of_quests": [
                q.model_dump() if hasattr(q, "model_dump") else q for q in quests
            ]
        }
        schedule_data = {
            "list_of_quests": [
                {"Name": q.Name, "Skills": q.Skills, "Week": q.Week}
                if hasattr(q, "Name")
                else q
                for q in quests
            ]
        }

        save_result = self.quest_service.update_quests_preserving_completed_data(
            schedule_data, homework_data, owner_id, period_id
        )
        logger.info(
            "PeriodSummerQuestService: quests persisted for user %s period %s",
            owner_id,
            period_id,
        )

        return {
            "message": f"Summer quests generated successfully for {len(quests)} weeks",
            "goal_text": goal_text,
            "saved_quests": save_result,
        }

    def run_as_background_task(self, owner_id: str, period_id: str) -> None:
        try:
            self.generate_summer_quests(owner_id=owner_id, period_id=period_id)
        except Exception as exc:
            logger.error(
                "Summer quest generation failed for period %s: %s", period_id, exc, exc_info=True
            )
            track_event(
                user_id=owner_id,
                event=Events.SUMMER_QUEST_GEN_FAILED,
                properties={"period_id": period_id, "error_type": type(exc).__name__},
            )
