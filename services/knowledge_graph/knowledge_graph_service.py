"""
KnowledgeGraphService — single entry point for reading and writing a
student's per-period knowledge graph.

Composes:
  * ConceptDAO / SkillDAO / ConceptSkillDAO  — normalized curriculum tables
  * StudentSkillMasteryDAO                  — per-student mastery layer

Used by REST routers and by agent function tools.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from data_access.concept_dao import ConceptDAO
from data_access.concept_skill_dao import ConceptSkillDAO
from data_access.skill_dao import SkillDAO
from data_access.student_skill_mastery_dao import StudentSkillMasteryDAO
from exceptions.validation_error import ValidationError
from models.student_skill_mastery import MASTERY_CUTOFF, StudentSkillMastery
from services.tracking.events import Events
from services.tracking.track import track_event

ConceptNode = dict
logger = logging.getLogger(__name__)


class KnowledgeGraphService:
    def __init__(
        self,
        concept_dao: Optional[ConceptDAO] = None,
        skill_dao: Optional[SkillDAO] = None,
        concept_skill_dao: Optional[ConceptSkillDAO] = None,
        student_skill_mastery_dao: Optional[StudentSkillMasteryDAO] = None,
        jwt: str | None = None,
    ) -> None:
        self.concept_dao = concept_dao or ConceptDAO(jwt=jwt)
        self.skill_dao = skill_dao or SkillDAO(jwt=jwt)
        self.concept_skill_dao = concept_skill_dao or ConceptSkillDAO(jwt=jwt)
        self.student_skill_mastery_dao = student_skill_mastery_dao or StudentSkillMasteryDAO(jwt=jwt)

    # -- internal helpers -----------------------------------------------------

    def _load_curriculum(self, period_id: str) -> dict:
        """Fetch normalized curriculum tables and build lookup structures."""
        concepts = self.concept_dao.get_concepts_by_period(period_id)
        skills = self.skill_dao.get_skills_by_period(period_id)
        cs_links = self.concept_skill_dao.get_all_for_period(period_id)

        # concept_name → [skill_name, ...]
        cs_by_concept: dict[str, list[str]] = {}
        for link in cs_links:
            cs_by_concept.setdefault(link["concept_name"], []).append(link["skill_name"])

        concepts_by_name = {c["concept_name"]: c for c in concepts}

        # skill_name → concept dict (first occurrence wins)
        skill_to_concept: dict[str, dict] = {}
        for cname, skill_names in cs_by_concept.items():
            concept = concepts_by_name.get(cname, {})
            for sname in skill_names:
                skill_to_concept.setdefault(sname, concept)

        # skill_name → mastery_threshold
        skill_thresholds = {
            s["skill_name"]: float(s.get("mastery_threshold") or MASTERY_CUTOFF)
            for s in skills
        }

        # prereq edges: cross-product of prereq-concept skills × dependent-concept skills
        prereq_edges: set[tuple[str, str]] = set()
        for concept in concepts:
            prereqs = concept.get("prerequisites") or []
            dep_skills = cs_by_concept.get(concept["concept_name"], [])
            for prereq_name in prereqs:
                for p in cs_by_concept.get(prereq_name, []):
                    for d in dep_skills:
                        if p != d:
                            prereq_edges.add((p, d))

        return {
            "skill_to_concept": skill_to_concept,
            "skill_thresholds": skill_thresholds,
            "prereq_edges": sorted(prereq_edges),
            "concepts_by_name": concepts_by_name,
            "cs_by_concept": cs_by_concept,
        }

    @staticmethod
    def _is_unlocked(
        concept: dict, mastered: set[str], cs_by_concept: dict[str, list[str]]
    ) -> bool:
        for prereq_name in (concept.get("prerequisites") or []):
            if any(s not in mastered for s in cs_by_concept.get(prereq_name, [])):
                return False
        return True

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
        curriculum = self._load_curriculum(period_id)
        skill_to_concept = curriculum["skill_to_concept"]
        skill_thresholds = curriculum["skill_thresholds"]
        prereq_edges = curriculum["prereq_edges"]

        mastery_rows = self.student_skill_mastery_dao.get_for_student(student_id, period_id)
        mastery_by_skill: dict[str, StudentSkillMastery] = {
            r.skill_name: r for r in mastery_rows
        }

        nodes: list[dict[str, Any]] = []
        seen: set[str] = set()
        for skill, concept in skill_to_concept.items():
            seen.add(skill)
            row = mastery_by_skill.get(skill)
            threshold = skill_thresholds.get(skill, MASTERY_CUTOFF)
            metadata = concept.get("metadata") or {}
            nodes.append(
                {
                    "skill": skill,
                    "score": row.score if row else 0.0,
                    "mastered": row.mastered if row else False,
                    "threshold": threshold,
                    "concept_name": concept.get("concept_name"),
                    "cognitive_load": metadata.get("cognitive_load"),
                }
            )

        # Skills with mastery rows but no longer in the curriculum.
        for skill, row in mastery_by_skill.items():
            if skill in seen:
                continue
            nodes.append(
                {
                    "skill": skill,
                    "score": row.score,
                    "mastered": row.mastered,
                    "threshold": skill_thresholds.get(skill, MASTERY_CUTOFF),
                    "concept_name": None,
                    "cognitive_load": None,
                }
            )

        edges = [{"from": p, "to": d} for p, d in prereq_edges]

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

        curriculum = self._load_curriculum(period_id)
        threshold = curriculum["skill_thresholds"].get(skill_name, MASTERY_CUTOFF)

        row = self.student_skill_mastery_dao.upsert_score(
            student_id=student_id,
            period_id=period_id,
            skill_name=skill_name,
            score=float(score),
            threshold=threshold,
        )

        try:
            skill_row = self.skill_dao.get_one_skill(period_id=period_id, skill_name=skill_name)
            if skill_row and skill_row.get("canonical_skill_id"):
                from models.adaptive.learning_event import LearningEvent
                from services.adaptive.learning_event_service import LearningEventService
                LearningEventService().write_event(
                    LearningEvent(
                        learner_id=student_id,
                        canonical_skill_id=skill_row["canonical_skill_id"],
                        event_type="embedded_check",
                        result="correct" if float(score) >= MASTERY_CUTOFF else "incorrect",
                    ),
                    period_id=period_id,
                    skill_name=skill_name,
                )
        except Exception:
            logger.warning(
                "adaptive event hook failed for student=%s period=%s skill=%s (non-fatal)",
                student_id, period_id, skill_name, exc_info=True,
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
        curriculum = self._load_curriculum(period_id)
        concepts_by_name = curriculum["concepts_by_name"]
        cs_by_concept = curriculum["cs_by_concept"]

        mastery_rows = self.student_skill_mastery_dao.get_for_student(student_id, period_id)
        mastered_skills = {r.skill_name for r in mastery_rows if r.mastered}

        return [
            concept
            for concept in concepts_by_name.values()
            if self._is_unlocked(concept, mastered_skills, cs_by_concept)
        ]
