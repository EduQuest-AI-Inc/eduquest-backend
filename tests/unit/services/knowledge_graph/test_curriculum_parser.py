import pytest

from models.student_skill_mastery import MASTERY_CUTOFF
from services.knowledge_graph import curriculum_parser


def _schedule():
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
                                "skills": ["assign_variable", "name_variable"],
                                "mastery_threshold": 0.8,
                                "cognitive_load": "low",
                            },
                            {
                                "concept_id": "C2",
                                "name": "Loops",
                                "prerequisites": ["C1"],
                                "skills": ["write_for_loop"],
                                "mastery_threshold": 0.85,
                                "cognitive_load": "medium",
                            },
                        ],
                    }
                ],
            },
            {
                "week": 2,
                "lessons": [
                    {
                        "lesson_id": "L2",
                        "concepts": [
                            {
                                "concept_id": "C3",
                                "name": "Functions",
                                "prerequisites": ["C2"],
                                "skills": ["define_function"],
                                # mastery_threshold deliberately omitted
                                "cognitive_load": "high",
                            }
                        ],
                    }
                ],
            },
        ]
    }


@pytest.mark.unit
def test_iter_concepts_walks_all_lessons():
    concepts = list(curriculum_parser.iter_concepts(_schedule()))
    assert [c["concept_id"] for c in concepts] == ["C1", "C2", "C3"]


@pytest.mark.unit
def test_all_skills_flattens():
    skills = curriculum_parser.all_skills(_schedule())
    assert skills == {"assign_variable", "name_variable", "write_for_loop", "define_function"}


@pytest.mark.unit
def test_mastery_threshold_uses_concept_value():
    assert curriculum_parser.mastery_threshold_for(_schedule(), "write_for_loop") == 0.85
    assert curriculum_parser.mastery_threshold_for(_schedule(), "assign_variable") == 0.8


@pytest.mark.unit
def test_mastery_threshold_falls_back_to_default():
    # define_function's concept omits mastery_threshold
    assert curriculum_parser.mastery_threshold_for(_schedule(), "define_function") == MASTERY_CUTOFF


@pytest.mark.unit
def test_mastery_threshold_unknown_skill_returns_default():
    assert curriculum_parser.mastery_threshold_for(_schedule(), "ghost_skill") == MASTERY_CUTOFF


@pytest.mark.unit
def test_prereq_skill_edges():
    edges = curriculum_parser.prereq_skill_edges(_schedule())
    # C1 → C2: every (assign_variable|name_variable) → write_for_loop
    # C2 → C3: write_for_loop → define_function
    assert ("assign_variable", "write_for_loop") in edges
    assert ("name_variable", "write_for_loop") in edges
    assert ("write_for_loop", "define_function") in edges
    # No phantom self-edges or backward edges
    assert ("define_function", "write_for_loop") not in edges


@pytest.mark.unit
def test_concept_is_unlocked_with_no_prereqs():
    schedule = _schedule()
    concepts = curriculum_parser.concepts_by_id(schedule)
    assert curriculum_parser.concept_is_unlocked(concepts["C1"], set(), concepts) is True


@pytest.mark.unit
def test_concept_is_unlocked_when_prereq_skills_mastered():
    schedule = _schedule()
    concepts = curriculum_parser.concepts_by_id(schedule)
    mastered = {"assign_variable", "name_variable"}
    assert curriculum_parser.concept_is_unlocked(concepts["C2"], mastered, concepts) is True


@pytest.mark.unit
def test_concept_is_locked_when_any_prereq_skill_missing():
    schedule = _schedule()
    concepts = curriculum_parser.concepts_by_id(schedule)
    mastered = {"assign_variable"}  # missing name_variable
    assert curriculum_parser.concept_is_unlocked(concepts["C2"], mastered, concepts) is False


@pytest.mark.unit
def test_parser_tolerates_garbage_input():
    # None, empty, wrong types should not raise
    assert list(curriculum_parser.iter_concepts(None)) == []
    assert curriculum_parser.all_skills({"weeks": "not-a-list"}) == set()
    assert curriculum_parser.prereq_skill_edges({"weeks": [{"lessons": [{"concepts": "x"}]}]}) == []
    assert curriculum_parser.mastery_threshold_for({}, "anything") == MASTERY_CUTOFF
