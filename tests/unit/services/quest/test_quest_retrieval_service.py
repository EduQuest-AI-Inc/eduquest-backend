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
