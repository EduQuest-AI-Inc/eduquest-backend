"""
OpenAI Agents SDK function tools for the per-student knowledge graph.

Any agent can opt in by extending its `tools=[...]` with these:

    from bots.tools.knowledge_graph_tools import KNOWLEDGE_GRAPH_TOOLS
    Agent(..., tools=[*KNOWLEDGE_GRAPH_TOOLS])

All tools take `student_id` and `period_id` explicitly so the same surface
works across grading, profile, LTG, and tutoring agents — none of them
need to share a context object.
"""
from __future__ import annotations

from typing import Any

from agents import function_tool

from services.knowledge_graph.knowledge_graph_service import KnowledgeGraphService


def _service() -> KnowledgeGraphService:
    return KnowledgeGraphService()


@function_tool
def get_student_skill_graph(student_id: str, period_id: str) -> dict[str, Any]:
    """Return the merged knowledge graph (nodes + edges) for one student in one period."""
    return _service().get_graph(student_id, period_id)


@function_tool
def get_skill_mastery(student_id: str, period_id: str, skill_name: str) -> dict[str, Any]:
    """Return the mastery row for a single skill. Returns a zeroed record if the skill isn't tracked yet."""
    return _service().get_skill_status(student_id, period_id, skill_name).to_item()


@function_tool
def update_skill_mastery(
    student_id: str, period_id: str, skill_name: str, score: float
) -> dict[str, Any]:
    """Upsert a mastery score in [0, 1]. The mastery threshold comes from the curriculum, not the caller."""
    return _service().update_mastery(student_id, period_id, skill_name, score).to_item()


@function_tool
def list_unlocked_concepts(student_id: str, period_id: str) -> list[dict[str, Any]]:
    """List concepts whose prerequisite skills the student has already mastered."""
    return [dict(c) for c in _service().get_unlocked_concepts(student_id, period_id)]


KNOWLEDGE_GRAPH_TOOLS = [
    get_student_skill_graph,
    get_skill_mastery,
    update_skill_mastery,
    list_unlocked_concepts,
]
