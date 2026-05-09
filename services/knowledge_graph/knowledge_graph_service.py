"""
KnowledgeGraphService — single entry point for reading and writing a
student's per-period knowledge graph.

Composes:
  * PeriodScheduleDAO  — the curriculum (concepts, prereqs, skills)
  * StudentSkillMasteryDAO — the per-student mastery layer
  * curriculum_parser — tolerant readers over schedule_json

Used by REST routers and by agent function tools.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from data_access.student_skill_mastery_dao import StudentSkillMasteryDAO
from exceptions.validation_error import ValidationError
from models.student_skill_mastery import StudentSkillMastery

ConceptNode = dict
from services.knowledge_graph import curriculum_parser
from services.tracking.events import Events
from services.tracking.track import track_event

logger = logging.getLogger(__name__)


class KnowledgeGraphService:
    def __init__(
        self,
        period_schedule_dao: Optional[Any] = None,
        student_skill_mastery_dao: Optional[StudentSkillMasteryDAO] = None,
    ) -> None:
        self.period_schedule_dao = period_schedule_dao
        self.student_skill_mastery_dao = student_skill_mastery_dao or StudentSkillMasteryDAO()

    # -- internal helpers -----------------------------------------------------

    def _schedule_json(self, period_id: str) -> dict:
        if self.period_schedule_dao is None:
            return {}
        schedule = self.period_schedule_dao.get_by_period_id(period_id)
        if schedule is None or not schedule.schedule_json:
            return {}
        return schedule.schedule_json

    # -- public API -----------------------------------------------------------

    def get_graph(self, student_id: str, period_id: str) -> dict[str, Any]:
        """
        Return the merged graph for one student in one period:
            {
              "nodes": [
                {
                  "skill": str,
                  "score": float,
                  "mastered": bool,
                  "threshold": float,
                  "concept_id": str | None,
                  "concept_name": str | None,
                  "cognitive_load": str | None,
                },
                ...
              ],
              "edges": [{"from": prereq_skill, "to": dependent_skill}, ...],
            }
        Skills present in the curriculum but not yet in the mastery table
        appear with score=0 and mastered=False.
        """
        schedule_json = self._schedule_json(period_id)
        skill_concept = curriculum_parser.skill_to_concept(schedule_json)

        mastery_rows = self.student_skill_mastery_dao.get_for_student(student_id, period_id)
        mastery_by_skill: dict[str, StudentSkillMastery] = {
            r.skill_name: r for r in mastery_rows
        }

        nodes: list[dict[str, Any]] = []
        seen: set[str] = set()
        for skill, concept in skill_concept.items():
            seen.add(skill)
            row = mastery_by_skill.get(skill)
            threshold = curriculum_parser.mastery_threshold_for(schedule_json, skill)
            nodes.append(
                {
                    "skill": skill,
                    "score": row.score if row else 0.0,
                    "mastered": row.mastered if row else False,
                    "threshold": threshold,
                    "concept_id": concept.get("concept_id"),
                    "concept_name": concept.get("name"),
                    "cognitive_load": concept.get("cognitive_load"),
                }
            )

        # Skills the student has mastery rows for but the curriculum no
        # longer mentions. Surface them so callers can spot drift.
        for skill, row in mastery_by_skill.items():
            if skill in seen:
                continue
            nodes.append(
                {
                    "skill": skill,
                    "score": row.score,
                    "mastered": row.mastered,
                    "threshold": curriculum_parser.mastery_threshold_for(schedule_json, skill),
                    "concept_id": None,
                    "concept_name": None,
                    "cognitive_load": None,
                }
            )

        edges = [
            {"from": p, "to": d}
            for p, d in curriculum_parser.prereq_skill_edges(schedule_json)
        ]

        return {"nodes": nodes, "edges": edges}

    def get_skill_status(
        self, student_id: str, period_id: str, skill_name: str
    ) -> StudentSkillMastery:
        """
        Return the mastery row for a skill. If the row doesn't exist yet,
        return a zeroed StudentSkillMastery (not yet persisted).
        """
        existing = self.student_skill_mastery_dao.get_one(student_id, period_id, skill_name)
        if existing is not None:
            return existing
        return StudentSkillMastery(
            student_id=student_id,
            period_id=period_id,
            skill_name=skill_name,
            score=0.0,
            mastered=False,
        )

    def update_mastery(
        self,
        student_id: str,
        period_id: str,
        skill_name: str,
        score: float,
    ) -> StudentSkillMastery:
        """
        Upsert a mastery score. Looks up the threshold from the curriculum
        so callers can't bypass it. Emits SKILL_MASTERY_UPDATED.
        """
        if not isinstance(score, (int, float)) or not 0.0 <= float(score) <= 1.0:
            raise ValidationError(f"score must be in [0, 1], got {score!r}")
        if not skill_name:
            raise ValidationError("skill_name is required")

        threshold = curriculum_parser.mastery_threshold_for(
            self._schedule_json(period_id), skill_name
        )
        row = self.student_skill_mastery_dao.upsert_score(
            student_id=student_id,
            period_id=period_id,
            skill_name=skill_name,
            score=float(score),
            threshold=threshold,
        )

        try:
            track_event(
                user_id=student_id,
                event=Events.SKILL_MASTERY_UPDATED,
                properties={
                    "period_id": period_id,
                    "score": row.score,
                    "mastered": row.mastered,
                    "threshold": threshold,
                },
            )
        except Exception:
            # track_event already swallows posthog errors; this guards
            # against any other unexpected import/runtime issue so a
            # write never fails because of analytics.
            logger.exception("track_event raised unexpectedly for skill_mastery_updated")

        return row

    def get_unlocked_concepts(
        self, student_id: str, period_id: str
    ) -> list[ConceptNode]:
        """
        Concepts whose every prerequisite-concept's skills are mastered
        by this student. Concepts with no prerequisites are always
        included.
        """
        schedule_json = self._schedule_json(period_id)
        concepts_by_id = curriculum_parser.concepts_by_id(schedule_json)

        mastery_rows = self.student_skill_mastery_dao.get_for_student(student_id, period_id)
        mastered_skills = {r.skill_name for r in mastery_rows if r.mastered}

        return [
            concept
            for concept in concepts_by_id.values()
            if curriculum_parser.concept_is_unlocked(concept, mastered_skills, concepts_by_id)
        ]
