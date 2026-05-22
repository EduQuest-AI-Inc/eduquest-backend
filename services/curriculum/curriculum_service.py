import asyncio
import concurrent.futures
import logging
import time
from datetime import date
from typing import Any

from fastapi import BackgroundTasks

from bots.protocol import BotProviderProtocol
from data_access.concept_dao import ConceptDAO
from data_access.concept_skill_dao import ConceptSkillDAO
from data_access.lesson_dao import LessonDAO
from data_access.period_dao import PeriodDAO
from data_access.skill_dao import SkillDAO
from data_access.week_dao import WeekDAO
from exceptions.not_found_error import NotFoundError
from exceptions.permission_error import PermissionError
from exceptions.validation_error import ValidationError
from integrations.perplexity_service import PerplexityService
from models.concept import Concept
from models.concept_skill import ConceptSkill
from models.lesson import Lesson
from models.skill import Skill
from models.week import Week

logger = logging.getLogger(__name__)

_VALID_STATUSES = {"pending", "draft", "approved"}


class CurriculumService:
    def __init__(
        self,
        *,
        bot_provider: BotProviderProtocol,
        period_dao=None,
        week_dao=None,
        lesson_dao=None,
        concept_dao=None,
        skill_dao=None,
        concept_skill_dao=None,
        perplexity_service=None,
        jwt: str | None = None,
    ) -> None:
        self._bot_provider = bot_provider
        self.period_dao = period_dao or PeriodDAO(jwt=jwt)
        self.week_dao = week_dao or WeekDAO(jwt=jwt)
        self.lesson_dao = lesson_dao or LessonDAO(jwt=jwt)
        self.concept_dao = concept_dao or ConceptDAO(jwt=jwt)
        self.skill_dao = skill_dao or SkillDAO(jwt=jwt)
        self.concept_skill_dao = concept_skill_dao or ConceptSkillDAO(jwt=jwt)
        self._perplexity_service = perplexity_service

    # ── public API ────────────────────────────────────────────────────────────

    def trigger_generation(self, period_id: str, background_tasks: BackgroundTasks) -> None:
        self._check_not_fork(period_id)
        period = self._get_period_or_raise(period_id)
        if period.get("status", "pending") not in {"pending", "failed"}:
            raise ValidationError(
                f"Cannot generate curriculum: period is already in '{period['status']}' status"
            )
        self.period_dao.update_status(period_id, "generating")
        background_tasks.add_task(self.run_generation, period_id)

    def get_curriculum(self, period_id: str, period: dict | None = None) -> dict[str, Any]:
        period = period or self._get_period_or_raise(period_id)
        fetchers = {
            "weeks": lambda: self.week_dao.get_weeks_by_period(period_id),
            "lessons": lambda: self.lesson_dao.get_lessons_by_period(period_id),
            "concepts": lambda: self.concept_dao.get_concepts_by_period(period_id),
            "skills": lambda: self.skill_dao.get_skills_by_period(period_id),
            "concept_skills": lambda: self.concept_skill_dao.get_all_for_period(period_id),
        }
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = {key: executor.submit(fn) for key, fn in fetchers.items()}
            results = {key: fut.result() for key, fut in futures.items()}
        return {"period_status": period["status"], **results}

    def save_curriculum(self, period_id: str, payload: dict[str, Any], period: dict | None = None) -> None:
        if period is None:
            self._get_period_or_raise(period_id)
        self._bulk_replace(period_id, payload)

    def update_concept(self, period_id: str, concept_name: str, fields: dict[str, Any], period: dict | None = None) -> None:
        if period is None:
            self._get_period_or_raise(period_id)
        existing = self.concept_dao.get_concept(period_id, concept_name)
        if not existing:
            raise NotFoundError(f"Concept '{concept_name}' not found in period '{period_id}'")
        self.concept_dao.update_concept(period_id, concept_name, fields)

    def update_skill(self, period_id: str, skill_name: str, fields: dict[str, Any], period: dict | None = None) -> None:
        if period is None:
            self._get_period_or_raise(period_id)
        self.skill_dao.update_skill(period_id, skill_name, fields)

    def approve_period(self, period_id: str, period: dict | None = None) -> list[dict[str, Any]]:
        if period is None:
            self._check_not_fork(period_id)
        period = period or self._get_period_or_raise(period_id)
        if period["status"] != "draft":
            raise ValidationError(
                f"Cannot approve: period status is '{period['status']}', must be 'draft'"
            )
        lessons = self.lesson_dao.get_lessons_by_period(period_id)
        self.period_dao.update_status(period_id, "approved")
        return lessons

    # ── private helpers ───────────────────────────────────────────────────────

    def _get_period_or_raise(self, period_id: str) -> dict[str, Any]:
        period = self.period_dao.get_period_by_id(period_id)
        if not period:
            raise NotFoundError(f"Period '{period_id}' not found")
        return period

    def _check_not_fork(self, period_id: str) -> None:
        period = self._get_period_or_raise(period_id)
        if period.get("forked_from_period_id"):
            raise PermissionError("Curriculum cannot be modified on a forked class")

    def run_generation(self, period_id: str) -> None:
        t0 = time.monotonic()
        mode = "unknown"
        try:
            period = self.period_dao.get_period_by_id(period_id)
            if not period:
                logger.error("run_generation: period %s not found", period_id)
                return

            self.period_dao.update_status(period_id, "generating")

            start_date = period.get("start_date") or date.today().isoformat()
            end_date = period.get("end_date") or date.today().isoformat()
            course_description = period.get("course_description") or period["name"]
            grade_level = period.get("grade_level")
            has_course_materials = bool(period.get("file_urls")) or bool(period.get("canvas_course_id"))
            vector_store_ids = (
                [period["vector_store_id"]]
                if period.get("vector_store_id") and has_course_materials
                else []
            )
            research_context = None

            if not vector_store_ids:
                try:
                    coverage = self._bot_provider.create_coverage_evaluator().evaluate(
                        course_name=period.get("name") or "",
                        course_description=course_description,
                        has_files=False,
                        grade_level=grade_level,
                    )
                    if not coverage.sufficient and coverage.research_queries:
                        queries = coverage.research_queries[:3]
                        perplexity_svc = self._perplexity_service or PerplexityService()
                        research_context = asyncio.run(
                            perplexity_svc.research(queries, max_steps=5)
                        )
                except Exception as e:
                    logger.warning(
                        "Curriculum research enrichment failed; falling back to description-only: %s",
                        e,
                    )

            mode = "files" if vector_store_ids else ("research" if research_context else "description")
            logger.info(
                "curriculum generation starting: period_id=%s mode=%s start=%s end=%s",
                period_id, mode, start_date, end_date,
            )

            bot = self._bot_provider.create_curriculum_agent(
                vector_store_ids=vector_store_ids,
                course_name=period.get("name") or "",
                start_date=str(start_date),
                end_date=str(end_date),
                course_description=course_description,
                grade_level=grade_level,
                research_context=research_context,
            )
            result = bot.run()

            elapsed = time.monotonic() - t0
            logger.info(
                "curriculum generation complete: period_id=%s mode=%s elapsed=%.1fs weeks=%d",
                period_id, mode, elapsed, len(result.weeks),
            )

            payload = self._curriculum_result_to_payload(period_id, result)
            self._bulk_replace(period_id, payload)
            self.period_dao.update_status(period_id, "draft")

        except Exception:
            elapsed = time.monotonic() - t0
            logger.exception(
                "curriculum generation failed: period_id=%s mode=%s elapsed=%.1fs",
                period_id, mode, elapsed,
            )
            try:
                self.period_dao.update_status(period_id, "failed")
            except Exception:
                logger.exception("could not set status=failed for period %s", period_id)
            raise

    def _curriculum_result_to_payload(self, period_id: str, result) -> dict[str, Any]:
        """Convert CurriculumResult (bot output) into the save_curriculum payload shape."""
        weeks = []
        lessons = []
        concepts = []
        skills: list[dict] = []
        concept_skills: list[dict] = []
        seen_skills: set[str] = set()

        for week in result.weeks:
            weeks.append({
                "week_number": week.week_number,
                "week_start": getattr(week, 'start_date', None),
                "week_end": getattr(week, 'end_date', None),
            })
            for lesson in week.lessons:
                lessons.append({
                    "lesson_name": lesson.title,
                    "week_number": week.week_number,
                })
                for concept in lesson.concepts:
                    concepts.append({
                        "concept_name": concept.title,
                        "lesson_name": lesson.title,
                        "description": getattr(concept, "description", None),
                        "prerequisites": getattr(concept, "prerequisites", []),
                        "key_takeaways": getattr(concept, "key_takeaways", []),
                        "common_misconceptions": getattr(concept, "common_misconceptions", []),
                    })
                    for skill in concept.skills:
                        if skill.title not in seen_skills:
                            skills.append({
                                "skill_name": skill.title,
                                "description": getattr(skill, "description", None),
                                "bloom_level": getattr(skill, "bloom_level", None),
                                "difficulty": getattr(skill, "difficulty", None),
                                "mastery_threshold": getattr(skill, "mastery_threshold", 0.8),
                            })
                            seen_skills.add(skill.title)
                        concept_skills.append({
                            "concept_name": concept.title,
                            "skill_name": skill.title,
                        })

        return {
            "weeks": weeks,
            "lessons": lessons,
            "concepts": concepts,
            "skills": skills,
            "concept_skills": concept_skills,
        }

    def _bulk_replace(self, period_id: str, payload: dict[str, Any]) -> None:
        """Delete all existing rows for the period and re-insert from payload."""
        self._delete_all(period_id)

        for w in payload.get("weeks", []):
            self.week_dao.insert_week(Week(
                period_id=period_id,
                week_number=w["week_number"],
                week_start=w.get("week_start") or None,
                week_end=w.get("week_end") or None,
            ))

        lesson_id_by_name: dict[str, str] = {}
        for ls in payload.get("lessons", []):
            lesson_id = self.lesson_dao.insert_lesson(Lesson(
                period_id=period_id,
                lesson_name=ls["lesson_name"],
                week_number=ls["week_number"],
            ))
            lesson_id_by_name[ls["lesson_name"]] = lesson_id

        for c in payload.get("concepts", []):
            self.concept_dao.insert_concept(Concept(
                period_id=period_id,
                concept_name=c["concept_name"],
                lesson_name=c["lesson_name"],
                lesson_id=lesson_id_by_name.get(c["lesson_name"]),
                description=c.get("description"),
                prerequisites=c.get("prerequisites") or [],
                key_takeaways=c.get("key_takeaways") or [],
                common_misconceptions=c.get("common_misconceptions") or [],
                metadata=c.get("metadata"),
            ))

        for s in payload.get("skills", []):
            self.skill_dao.insert_skill(Skill(
                period_id=period_id,
                skill_name=s["skill_name"],
                description=s.get("description"),
                bloom_level=s.get("bloom_level"),
                difficulty=s.get("difficulty"),
                mastery_threshold=s.get("mastery_threshold", 0.8),
                mastery_criteria=s.get("mastery_criteria"),
                metadata=s.get("metadata"),
            ))

        for cs in payload.get("concept_skills", []):
            self.concept_skill_dao.insert_concept_skill(ConceptSkill(
                period_id=period_id,
                concept_name=cs["concept_name"],
                skill_name=cs["skill_name"],
            ))

    def _delete_all(self, period_id: str) -> None:
        """Delete all curriculum rows for a period in dependency order."""
        self.concept_skill_dao.delete_all_for_period(period_id)
        self.concept_dao.delete_all_for_period(period_id)
        self.skill_dao.delete_all_for_period(period_id)
        self.lesson_dao.delete_all_for_period(period_id)
        self.week_dao.delete_weeks_by_period(period_id)
