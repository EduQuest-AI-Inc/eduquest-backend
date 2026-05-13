import asyncio
import logging
import os
from typing import Any

from fastapi import BackgroundTasks

from bots.protocol import BotProviderProtocol
from data_access.concept_dao import ConceptDAO
from data_access.concept_skill_dao import ConceptSkillDAO
from data_access.lesson_dao import LessonDAO
from data_access.lesson_pptx_dao import LessonPptxDAO
from data_access.period_dao import PeriodDAO
from data_access.skill_dao import SkillDAO
from exceptions.validation_error import ValidationError
from integrations import s3_service
from models.lesson_pptx import LessonPptx

logger = logging.getLogger(__name__)

_SEMAPHORE_LIMIT = 8


class PptxGenerationService:
    def __init__(
        self,
        *,
        bot_provider: BotProviderProtocol,
        lesson_pptx_dao=None,
        period_dao=None,
        lesson_dao=None,
        concept_dao=None,
        skill_dao=None,
        concept_skill_dao=None,
        s3=None,
    ) -> None:
        self._bot_provider = bot_provider
        self.lesson_pptx_dao = lesson_pptx_dao or LessonPptxDAO()
        self.period_dao = period_dao or PeriodDAO()
        self.lesson_dao = lesson_dao or LessonDAO()
        self.concept_dao = concept_dao or ConceptDAO()
        self.skill_dao = skill_dao or SkillDAO()
        self.concept_skill_dao = concept_skill_dao or ConceptSkillDAO()
        self._s3 = s3 or s3_service

    def start_batch(
        self,
        period_id: str,
        background_tasks: BackgroundTasks,
        lessons: list[dict[str, Any]],
    ) -> int:
        """Create LessonPptx records and schedule background generation.

        Raises ValidationError if generation is already running or completed.
        Returns the number of lessons queued.
        """
        if self.lesson_pptx_dao.get_by_period(period_id):
            raise ValidationError("Generation already running or completed for this period")

        for lesson in lessons:
            self.lesson_pptx_dao.insert(LessonPptx(
                lesson_id=lesson["lesson_id"],
                period_id=period_id,
                status="pending",
            ))

        background_tasks.add_task(self.run_batch, period_id)
        return len(lessons)

    def run_batch(self, period_id: str) -> None:
        """Sync entry point for BackgroundTasks. Reads state then drives the async batch."""
        period = self.period_dao.get_period_by_id(period_id)
        period_context = {
            "period_name": period.get("name", "") if period else "",
            "grade_level": period.get("grade_level", "") if period else "",
            "course_name": period.get("canvas_course_name", "") if period else "",
            "course_description": period.get("course_description", "") if period else "",
        }

        pptx_rows = self.lesson_pptx_dao.get_by_period(period_id)
        logger.info("pptx batch starting: period=%s lessons=%d", period_id, len(pptx_rows))
        curriculum = {
            "lessons": self.lesson_dao.get_lessons_by_period(period_id),
            "concepts": self.concept_dao.get_concepts_by_period(period_id),
            "skills": self.skill_dao.get_skills_by_period(period_id),
            "concept_skills": self.concept_skill_dao.get_all_for_period(period_id),
        }
        asyncio.run(self._run_batch_async(pptx_rows, curriculum, period_context))
        logger.info("pptx batch complete: period=%s", period_id)

    async def _run_batch_async(
        self,
        pptx_rows: list[dict[str, Any]],
        curriculum: dict[str, Any],
        period_context: dict[str, Any],
    ) -> None:
        sem = asyncio.Semaphore(_SEMAPHORE_LIMIT)
        await asyncio.gather(
            *[self._generate_one(row, curriculum, period_context, sem) for row in pptx_rows]
        )

    async def _generate_one(
        self,
        row: dict[str, Any],
        curriculum: dict[str, Any],
        period_context: dict[str, Any],
        sem: asyncio.Semaphore,
    ) -> None:
        async with sem:
            pptx_id = row["pptx_id"]
            lesson_id = row["lesson_id"]

            lesson = next(
                (les for les in curriculum["lessons"] if les.get("lesson_id") == lesson_id),
                None,
            )
            if not lesson:
                logger.error("pptx generation: lesson %s not found in curriculum", lesson_id)
                self.lesson_pptx_dao.update_status(pptx_id, {"status": "failed"})
                return

            concepts = [
                c for c in curriculum["concepts"]
                if c.get("lesson_name") == lesson["lesson_name"]
            ]
            concept_names = {c["concept_name"] for c in concepts}
            skills = [
                skill for skill in curriculum["skills"]
                if any(
                    cs["concept_name"] in concept_names and cs["skill_name"] == skill["skill_name"]
                    for cs in curriculum["concept_skills"]
                )
            ]

            lesson_with_context = {
                **lesson,
                "concepts": concepts,
                "skills": skills,
            }

            logger.info("pptx generating: lesson=%s name=%r", lesson_id, lesson.get("lesson_name"))
            self.lesson_pptx_dao.update_status(pptx_id, {"status": "generating"})
            try:
                result = await self._bot_provider.create_pptx_agent().run(
                    lesson_with_context, period_context
                )
                pptx_bytes = result["pptx_bytes"]
                html_str = result.get("html_str", "")

                pptx_key = self._s3.upload_pptx(pptx_bytes, row["period_id"], lesson_id)
                fields: dict[str, Any] = {"status": "done", "s3_key": pptx_key}

                if html_str:
                    html_key = self._s3.upload_html(html_str, row["period_id"], lesson_id)
                    fields["html_key"] = html_key

                self.lesson_pptx_dao.update_status(pptx_id, fields)
                logger.info("pptx done: lesson=%s", lesson_id)
            except Exception as exc:
                if os.getenv("PYTEST_CURRENT_TEST"):
                    raise
                logger.error(
                    "pptx generation failed for lesson %s: %s: %s",
                    lesson_id, type(exc).__name__, exc,
                    exc_info=True,
                )
                self.lesson_pptx_dao.update_status(pptx_id, {"status": "failed"})
