import pytest
from unittest.mock import MagicMock, patch

from services.quest.quest_service import QuestService


SCHEDULE_1 = {
    "list_of_quests": [
        {"Name": "Quest 1", "Skills": "algebra", "Week": 1},
        {"Name": "Quest 2", "Skills": "geometry", "Week": 2},
    ]
}
HOMEWORK_1 = {
    "list_of_quests": [
        {"Name": "Quest A", "Skills": "reading", "Week": 1,
         "instructions": "Read chapter 3", "rubric": {"criteria": "accuracy"}},
    ]
}


def _svc():
    svc = QuestService.__new__(QuestService)
    svc._creation = MagicMock()
    svc._retrieval = MagicMock()
    svc._grading = MagicMock()
    return svc


@pytest.mark.unit
def test_quest_service_save_quests_from_schedule_delegates():
    svc = _svc()
    svc.save_quests_from_schedule(SCHEDULE_1, "u1", "p1")
    svc._creation.save_quests_from_schedule.assert_called_once_with(SCHEDULE_1, "u1", "p1")


@pytest.mark.unit
def test_quest_service_create_quests_from_homework_delegates():
    svc = _svc()
    svc.create_quests_from_homework(HOMEWORK_1, "u2", "p2")
    svc._creation.create_quests_from_homework.assert_called_once_with(HOMEWORK_1, "u2", "p2")


@pytest.mark.unit
def test_quest_service_get_quests_for_student_delegates():
    svc = _svc()
    svc.get_quests_for_student("u1")
    svc._retrieval.get_quests_for_student.assert_called_once_with("u1")


@pytest.mark.unit
def test_quest_service_get_quests_for_student_and_period_delegates():
    svc = _svc()
    svc.get_quests_for_student_and_period("u1", "p1")
    svc._retrieval.get_quests_for_student_and_period.assert_called_once_with("u1", "p1")


@pytest.mark.unit
def test_quest_service_get_quest_by_id_delegates():
    svc = _svc()
    svc.get_quest_by_id("qid1")
    svc._retrieval.get_quest_by_id.assert_called_once_with("qid1")


@pytest.mark.unit
def test_quest_service_verify_quest_structure_delegates():
    svc = _svc()
    svc.verify_quest_structure("u1", "p1")
    svc._retrieval.verify_quest_structure.assert_called_once_with("u1", "p1")


@pytest.mark.unit
def test_quest_service_update_quest_status_delegates():
    svc = _svc()
    svc.update_quest_status("qid1", "completed")
    svc._grading.update_quest_status.assert_called_once_with("qid1", "completed")


@pytest.mark.unit
def test_quest_service_update_quests_preserving_completed_data_delegates():
    svc = _svc()
    svc.update_quests_preserving_completed_data(SCHEDULE_1, HOMEWORK_1, "u1", "p1")
    svc._grading.update_quests_preserving_completed_data.assert_called_once_with(
        SCHEDULE_1, HOMEWORK_1, "u1", "p1"
    )


@pytest.mark.unit
def test_quest_service_delegation_returns_sub_service_value():
    svc = _svc()
    svc._retrieval.get_quest_by_id.return_value = {"quest_id": "qid1"}
    result = svc.get_quest_by_id("qid1")
    assert result == {"quest_id": "qid1"}


@pytest.mark.unit
def test_quest_service_parse_grade_data_delegates_to_retrieval_static():
    with patch("services.quest.quest_service.QuestRetrievalService.parse_grade_data", return_value={"score": 90}) as mock_parse:
        result = QuestService.parse_grade_data({"overall_score": "90"})
    mock_parse.assert_called_once()
    assert result == {"score": 90}


@pytest.mark.unit
def test_quest_service_format_grade_for_display_delegates_to_retrieval_static():
    with patch("services.quest.quest_service.QuestRetrievalService.format_grade_for_display", return_value="A+") as mock_fmt:
        result = QuestService.format_grade_for_display({"overall_score": "95"})
    mock_fmt.assert_called_once()
    assert result == "A+"
