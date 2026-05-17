import pytest
from unittest.mock import MagicMock

from services.quest.quest_retrieval_service import QuestRetrievalService


# --- pure-function tests (no DAO needed) ---

@pytest.mark.unit
def test_parse_grade_data_none():
    result = QuestRetrievalService.parse_grade_data(None)

    assert result["display_grade"] == "Not graded"
    assert result["detailed_grade"] is None
    assert result["overall_score"] is None


@pytest.mark.unit
def test_parse_grade_data_legacy_string():
    result = QuestRetrievalService.parse_grade_data("88")

    assert result["overall_score"] == "88", f"expected '88', got {result['overall_score']!r}"
    assert result["detailed_grade"] is None


@pytest.mark.unit
def test_parse_grade_data_dict_with_detailed_grade():
    grade = {"overall_score": "92/100", "detailed_grade": {"algebra": 0.9}}
    result = QuestRetrievalService.parse_grade_data(grade)

    assert result["overall_score"] == "92/100"
    assert result["detailed_grade"] == {"algebra": 0.9}


# --- DAO-mocking tests ---

def _svc():
    svc = QuestRetrievalService.__new__(QuestRetrievalService)
    svc.quest_dao = MagicMock()
    return svc


@pytest.mark.unit
def test_get_quests_for_student_and_period():
    svc = _svc()
    svc.quest_dao.get_quests_by_student_and_period.return_value = [{"quest_id": "q1"}]

    result = svc.get_quests_for_student_and_period("u1", "p1")

    svc.quest_dao.get_quests_by_student_and_period.assert_called_once_with("u1", "p1")
    assert result == [{"quest_id": "q1"}]


@pytest.mark.unit
def test_verify_quest_structure_no_weekly_quest():
    svc = _svc()
    svc.quest_dao.get_quests_by_student_and_period.return_value = []

    result = svc.verify_quest_structure("u1", "p1")

    assert "error" in result, f"expected 'error' key, got {result!r}"


@pytest.mark.unit
def test_verify_quest_structure_success():
    svc = _svc()
    svc.quest_dao.get_quests_by_student_and_period.return_value = [
        {"quest_id": "q1", "week": 1},
        {"quest_id": "q2", "week": 2},
    ]

    result = svc.verify_quest_structure("u1", "p1")

    assert "quests" in result, f"expected 'quests' key, got {result!r}"
    assert result["quests"]["total_count"] == 2
    assert "quest_ids" in result["quests"]
    assert "weeks" in result["quests"]


# ── parse_grade_data edge cases ────────────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.parametrize("grade,expected_score,expected_display", [
    ({}, "Score not available", "Score not available"),   # empty dict — no overall_score key
    (0,   "0",    "0"),                                   # integer zero (falsy) → legacy string path
    (3.14, "3.14", "3.14"),                               # float → legacy string path
    ([],  "[]",   "[]"),                                  # list → legacy string path
])
def test_parse_grade_data_edge_cases(grade, expected_score, expected_display):
    result = QuestRetrievalService.parse_grade_data(grade)
    assert result["overall_score"] == expected_score, (
        f"grade={grade!r}: expected overall_score={expected_score!r}, got {result['overall_score']!r}"
    )
    assert result["display_grade"] == expected_display, (
        f"grade={grade!r}: expected display_grade={expected_display!r}, got {result['display_grade']!r}"
    )


@pytest.mark.unit
def test_parse_grade_data_dict_missing_overall_score():
    """Dict with only detailed_grade key — overall_score falls back to sentinel."""
    grade = {"detailed_grade": {"algebra": 0.85}}
    result = QuestRetrievalService.parse_grade_data(grade)
    assert result["overall_score"] == "Score not available"
    assert result["detailed_grade"] == {"algebra": 0.85}
