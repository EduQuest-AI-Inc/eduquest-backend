import asyncio
import logging
from typing import Any

from data_access.lesson_pptx_dao import LessonPptxDAO
from integrations import s3_service

logger = logging.getLogger(__name__)

_SEMAPHORE_LIMIT = 8


class PptxGenerationService:
    def __init__(self) -> None:
        self.lesson_pptx_dao = LessonPptxDAO()

    def run_batch(self, period_id: str) -> None:
        """Sync entry point for BackgroundTasks. Fetches state then drives the async batch."""
        from services.curriculum.curriculum_service import CurriculumService
        pptx_rows = self.lesson_pptx_dao.get_by_period(period_id)
        curriculum = CurriculumService().get_curriculum(period_id)
        asyncio.run(self._run_batch_async(pptx_rows, curriculum))

    async def _run_batch_async(
        self, pptx_rows: list[dict[str, Any]], curriculum: dict[str, Any]
    ) -> None:
        sem = asyncio.Semaphore(_SEMAPHORE_LIMIT)
        await asyncio.gather(*[self._generate_one(row, curriculum, sem) for row in pptx_rows])

    async def _generate_one(
        self,
        row: dict[str, Any],
        curriculum: dict[str, Any],
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
                s for s in curriculum["skills"]
                if any(
                    cs["concept_name"] in concept_names and cs["skill_name"] == s["skill_name"]
                    for cs in curriculum["concept_skills"]
                )
            ]

            self.lesson_pptx_dao.update_status(pptx_id, {"status": "generating"})
            try:
                from bots.pptx_agent import PptxAgent
                pptx_bytes = await PptxAgent().run(lesson, concepts, skills)
                s3_key = s3_service.upload_pptx(pptx_bytes, row["period_id"], lesson_id)
                self.lesson_pptx_dao.update_status(pptx_id, {"status": "done", "s3_key": s3_key})
            except Exception as e:
                logger.error("pptx generation failed for lesson %s: %s", lesson_id, e)
                self.lesson_pptx_dao.update_status(pptx_id, {"status": "failed"})
