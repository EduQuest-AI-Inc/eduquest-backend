"""
Tolerant readers over `period_schedule.schedule_json`.

The cofounder's class-creation agent emits a tree of weeks → lessons → concepts.
The exact shape may keep evolving while the agent matures, so every helper
here:

  * Treats every nested field as optional.
  * Skips entries that don't match the expected shape rather than raising.
  * Falls back to extracting whatever skill names are present.

Never reach into `schedule_json` directly from a service or a route — go
through these helpers so the rest of the backend has one place to update
when the schema evolves.
"""
from __future__ import annotations

from typing import Any, Iterable, Iterator, Optional

from models.period_schedule import ConceptNode
from models.student_skill_mastery import MASTERY_CUTOFF


def _safe_list(value: Any) -> list:
    return value if isinstance(value, list) else []


def _safe_dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def iter_concepts(schedule_json: Optional[dict]) -> Iterator[ConceptNode]:
    """Walk weeks → lessons → concepts and yield each concept dict."""
    schedule = _safe_dict(schedule_json)
    for week in _safe_list(schedule.get("weeks")):
        week_d = _safe_dict(week)
        for lesson in _safe_list(week_d.get("lessons")):
            lesson_d = _safe_dict(lesson)
            for concept in _safe_list(lesson_d.get("concepts")):
                if isinstance(concept, dict):
                    yield concept  # type: ignore[misc]


def all_skills(schedule_json: Optional[dict]) -> set[str]:
    """Flat set of every skill name across the period."""
    skills: set[str] = set()
    for concept in iter_concepts(schedule_json):
        for skill in _safe_list(concept.get("skills")):
            if isinstance(skill, str) and skill:
                skills.add(skill)
    return skills


def skill_to_concept(schedule_json: Optional[dict]) -> dict[str, ConceptNode]:
    """
    Map skill name → the concept that owns it.

    If the same skill appears in multiple concepts, the first occurrence wins.
    """
    mapping: dict[str, ConceptNode] = {}
    for concept in iter_concepts(schedule_json):
        for skill in _safe_list(concept.get("skills")):
            if isinstance(skill, str) and skill and skill not in mapping:
                mapping[skill] = concept
    return mapping


def mastery_threshold_for(schedule_json: Optional[dict], skill_name: str) -> float:
    """
    Return the mastery threshold (0.0–1.0) of the concept that owns the skill.
    Falls back to MASTERY_CUTOFF if the skill isn't found or the concept
    omits the threshold.
    """
    concept = skill_to_concept(schedule_json).get(skill_name)
    if not concept:
        return MASTERY_CUTOFF
    threshold = concept.get("mastery_threshold")
    if isinstance(threshold, (int, float)):
        return float(threshold)
    return MASTERY_CUTOFF


def prereq_skill_edges(schedule_json: Optional[dict]) -> list[tuple[str, str]]:
    """
    Derive skill-level prerequisite edges from the concept graph.

    For every concept C with prerequisites [P1, P2, ...]:
      for every skill `s` in C and every skill `p` in any Pi:
        emit (p, s)  — meaning `p` must be learned before `s`.

    Returns a list of (prereq_skill, dependent_skill) tuples, deduped.
    """
    concepts_by_id: dict[str, ConceptNode] = {}
    for concept in iter_concepts(schedule_json):
        cid = concept.get("concept_id")
        if isinstance(cid, str) and cid:
            concepts_by_id[cid] = concept

    edges: set[tuple[str, str]] = set()
    for concept in concepts_by_id.values():
        dependent_skills = [
            s for s in _safe_list(concept.get("skills")) if isinstance(s, str) and s
        ]
        for prereq_id in _safe_list(concept.get("prerequisites")):
            prereq_concept = concepts_by_id.get(prereq_id) if isinstance(prereq_id, str) else None
            if not prereq_concept:
                continue
            prereq_skills = [
                s
                for s in _safe_list(prereq_concept.get("skills"))
                if isinstance(s, str) and s
            ]
            for p in prereq_skills:
                for d in dependent_skills:
                    if p != d:
                        edges.add((p, d))
    return sorted(edges)


def concept_is_unlocked(
    concept: ConceptNode,
    mastered_skills: Iterable[str],
    concepts_by_id: dict[str, ConceptNode],
) -> bool:
    """
    A concept is unlocked when every skill in every prerequisite concept
    is in `mastered_skills`. A concept with no prerequisites is always
    unlocked.
    """
    mastered = set(mastered_skills)
    for prereq_id in _safe_list(concept.get("prerequisites")):
        prereq_concept = concepts_by_id.get(prereq_id) if isinstance(prereq_id, str) else None
        if not prereq_concept:
            # Unknown prereq id — be conservative and treat as unsatisfied.
            return False
        prereq_skills = [
            s for s in _safe_list(prereq_concept.get("skills")) if isinstance(s, str) and s
        ]
        if any(s not in mastered for s in prereq_skills):
            return False
    return True


def concepts_by_id(schedule_json: Optional[dict]) -> dict[str, ConceptNode]:
    """Return concepts keyed by their concept_id (skipping any without one)."""
    out: dict[str, ConceptNode] = {}
    for concept in iter_concepts(schedule_json):
        cid = concept.get("concept_id")
        if isinstance(cid, str) and cid:
            out[cid] = concept
    return out
