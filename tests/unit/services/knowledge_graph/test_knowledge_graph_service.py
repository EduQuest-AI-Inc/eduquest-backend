from unittest.mock import MagicMock

import pytest

from exceptions.validation_error import ValidationError
from models.period_schedule import PeriodSchedule
from models.student_skill_mastery import MASTERY_CUTOFF, StudentSkillMastery
from services.knowledge_graph.knowledge_graph_service import KnowledgeGraphService


def _schedule_payload():
    return {
        "weeks": [
            {
                "week": 1,
                "lessons": [
                    {
                        "lesson_id": "L1",
                        "concepts": [
                            {
                                "concept_id": "C1",
                                "name": "Variables",
                                "prerequisites": [],
                                "skills": ["assign_variable"],
                                "mastery_threshold": 0.8,
                                "cognitive_load": "low",
                            },
                            {
                                "concept_id": "C2",
                                "name": "Loops",
                                "prerequisites": ["C1"],
                                "skills": ["write_for_loop"],
                                "mastery_threshold": 0.9,
                                "cognitive_load": "medium",
                            },
                        ],
                    }
                ],
            }
        ]
    }


def _service(period_dao=None, mastery_dao=None) -> KnowledgeGraphService:
    schedule_dao = period_dao or MagicMock()
    if period_dao is None:
        schedule_dao.get_by_period_id.return_value = PeriodSchedule(
            period_id="p1", schedule_json=_schedule_payload()
        )
    return KnowledgeGraphService(
        period_schedule_dao=schedule_dao,
        student_skill_mastery_dao=mastery_dao or MagicMock(),
    )


@pytest.mark.unit
def test_get_graph_zeroes_unscored_skills():
    mastery_dao = MagicMock()
    mastery_dao.get_for_student.return_value = []
    svc = _service(mastery_dao=mastery_dao)

    graph = svc.get_graph("s1", "p1")

    skills = {n["skill"]: n for n in graph["nodes"]}
    assert skills["assign_variable"]["score"] == 0.0
    assert skills["assign_variable"]["mastered"] is False
    assert skills["assign_variable"]["threshold"] == 0.8
    assert skills["write_for_loop"]["threshold"] == 0.9
    # edge from C1's skill to C2's skill
    assert {"from": "assign_variable", "to": "write_for_loop"} in graph["edges"]


@pytest.mark.unit
def test_get_graph_merges_mastery_rows():
    mastery_dao = MagicMock()
    mastery_dao.get_for_student.return_value = [
        StudentSkillMastery(
            student_id="s1",
            period_id="p1",
            skill_name="assign_variable",
            score=0.95,
            mastered=True,
        )
    ]
    svc = _service(mastery_dao=mastery_dao)

    graph = svc.get_graph("s1", "p1")
    skills = {n["skill"]: n for n in graph["nodes"]}

    assert skills["assign_variable"]["score"] == 0.95
    assert skills["assign_variable"]["mastered"] is True
    assert skills["write_for_loop"]["mastered"] is False


@pytest.mark.unit
def test_get_graph_surfaces_orphan_mastery_rows():
    mastery_dao = MagicMock()
    mastery_dao.get_for_student.return_value = [
        StudentSkillMastery(
            student_id="s1",
            period_id="p1",
            skill_name="orphaned_skill",
            score=0.6,
            mastered=False,
        )
    ]
    svc = _service(mastery_dao=mastery_dao)

    graph = svc.get_graph("s1", "p1")
    orphan = next(n for n in graph["nodes"] if n["skill"] == "orphaned_skill")
    assert orphan["concept_id"] is None
    assert orphan["threshold"] == MASTERY_CUTOFF


@pytest.mark.unit
def test_update_mastery_uses_curriculum_threshold():
    mastery_dao = MagicMock()
    captured = {}

    def fake_upsert(student_id, period_id, skill_name, score, threshold):
        captured.update(
            student_id=student_id,
            period_id=period_id,
            skill_name=skill_name,
            score=score,
            threshold=threshold,
        )
        return StudentSkillMastery(
            student_id=student_id,
            period_id=period_id,
            skill_name=skill_name,
            score=score,
            mastered=score >= threshold,
        )

    mastery_dao.upsert_score.side_effect = fake_upsert
    svc = _service(mastery_dao=mastery_dao)

    row = svc.update_mastery("s1", "p1", "write_for_loop", 0.92)

    assert captured["threshold"] == 0.9  # comes from concept C2
    assert row.mastered is True


@pytest.mark.unit
def test_update_mastery_below_threshold_not_mastered():
    mastery_dao = MagicMock()
    mastery_dao.upsert_score.side_effect = lambda **kw: StudentSkillMastery(
        student_id=kw["student_id"],
        period_id=kw["period_id"],
        skill_name=kw["skill_name"],
        score=kw["score"],
        mastered=kw["score"] >= kw["threshold"],
    )
    svc = _service(mastery_dao=mastery_dao)

    row = svc.update_mastery("s1", "p1", "write_for_loop", 0.5)

    assert row.mastered is False


@pytest.mark.unit
@pytest.mark.parametrize("bad_score", [-0.01, 1.5, "high", None])
def test_update_mastery_rejects_out_of_range(bad_score):
    svc = _service()
    with pytest.raises(ValidationError):
        svc.update_mastery("s1", "p1", "x", bad_score)  # type: ignore[arg-type]


@pytest.mark.unit
def test_update_mastery_rejects_empty_skill_name():
    svc = _service()
    with pytest.raises(ValidationError):
        svc.update_mastery("s1", "p1", "", 0.5)


@pytest.mark.unit
def test_get_skill_status_returns_zeroed_when_missing():
    mastery_dao = MagicMock()
    mastery_dao.get_one.return_value = None
    svc = _service(mastery_dao=mastery_dao)

    status = svc.get_skill_status("s1", "p1", "assign_variable")
    assert status.score == 0.0
    assert status.mastered is False


@pytest.mark.unit
def test_get_unlocked_concepts_only_returns_ready_concepts():
    mastery_dao = MagicMock()
    mastery_dao.get_for_student.return_value = []  # nothing mastered yet
    svc = _service(mastery_dao=mastery_dao)

    unlocked = svc.get_unlocked_concepts("s1", "p1")
    ids = {c["concept_id"] for c in unlocked}

    # Only C1 has no prereqs and is therefore unlocked initially.
    assert ids == {"C1"}


@pytest.mark.unit
def test_get_unlocked_concepts_after_mastering_prereqs():
    mastery_dao = MagicMock()
    mastery_dao.get_for_student.return_value = [
        StudentSkillMastery(
            student_id="s1",
            period_id="p1",
            skill_name="assign_variable",
            score=1.0,
            mastered=True,
        )
    ]
    svc = _service(mastery_dao=mastery_dao)

    unlocked = svc.get_unlocked_concepts("s1", "p1")
    ids = {c["concept_id"] for c in unlocked}
    assert ids == {"C1", "C2"}


@pytest.mark.unit
def test_empty_schedule_does_not_blow_up():
    period_dao = MagicMock()
    period_dao.get_by_period_id.return_value = None
    mastery_dao = MagicMock()
    mastery_dao.get_for_student.return_value = []
    svc = KnowledgeGraphService(
        period_schedule_dao=period_dao,
        student_skill_mastery_dao=mastery_dao,
    )

    graph = svc.get_graph("s1", "p1")
    assert graph == {"nodes": [], "edges": []}
    assert svc.get_unlocked_concepts("s1", "p1") == []
