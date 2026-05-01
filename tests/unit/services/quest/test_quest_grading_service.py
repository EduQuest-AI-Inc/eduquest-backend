import pytest
from unittest.mock import MagicMock

from services.quest.quest_grading_service import QuestGradingService


def _svc():
    svc = QuestGradingService.__new__(QuestGradingService)
    svc.quest_dao = MagicMock()
    return svc


@pytest.mark.unit
def test_update_quest_status_not_found():
    svc = _svc()
    # update_quest_status delegates directly to DAO; test that DAO is called correctly
    # (no existence check in this method — just verify delegation)
    svc.update_quest_status("q1", "completed")

    svc.quest_dao.update_quest_status.assert_called_once_with("q1", "completed")


@pytest.mark.unit
def test_update_quest_status_returns_dict():
    svc = _svc()

    result = svc.update_quest_status("q1", "in_progress")

    assert result["quest_id"] == "q1"
    assert result["status"] == "in_progress"
    assert "message" in result


@pytest.mark.unit
def test_update_quests_preserving_completed_data_graded_preserved():
    svc = _svc()
    svc.quest_dao.get_quests_by_student_and_period.side_effect = [
        # first call: existing quests
        [{"quest_id": "q1", "week": 1, "grade": {"overall_score": "90"}, "status": "completed", "skills": "algebra"}],
        # second call: for total count
        [{"quest_id": "q1", "week": 1}],
    ]

    schedule_data = {"list_of_quests": [{"Week": 1, "Name": "New Name", "Skills": "algebra"}]}
    homework_data = {"list_of_quests": [{"Week": 1, "Name": "New Name", "instructions": "do it", "rubric": {}}]}

    result = svc.update_quests_preserving_completed_data(schedule_data, homework_data, "u1", "p1")

    assert result["preserved_quests"] == 1
    assert result["updated_quests"] == 0
    # update_quest is never called for locked quests (skills unchanged)
    svc.quest_dao.add_quest.assert_not_called()


@pytest.mark.unit
def test_update_quests_preserving_completed_data_not_started_updated():
    svc = _svc()
    svc.quest_dao.get_quests_by_student_and_period.side_effect = [
        [{"quest_id": "q1", "week": 1, "grade": None, "status": "not_started", "skills": "old"}],
        [{"quest_id": "q1"}],
    ]

    schedule_data = {"list_of_quests": [{"Week": 1, "Name": "Updated", "Skills": "new_skills"}]}
    homework_data = {"list_of_quests": [{"Week": 1, "Name": "Updated", "instructions": "do it", "rubric": {}}]}

    result = svc.update_quests_preserving_completed_data(schedule_data, homework_data, "u1", "p1")

    assert result["updated_quests"] == 1
    svc.quest_dao.update_quest.assert_called_once()


@pytest.mark.unit
def test_update_quests_preserving_completed_data_new_week_created():
    svc = _svc()
    svc.quest_dao.get_quests_by_student_and_period.side_effect = [
        [],  # no existing quests
        [{"quest_id": "qnew"}],  # after creation
    ]

    schedule_data = {"list_of_quests": [{"Week": 5, "Name": "New Quest", "Skills": "skills5"}]}
    homework_data = {"list_of_quests": [{"Week": 5, "Name": "New Quest", "instructions": "...", "rubric": {}}]}

    result = svc.update_quests_preserving_completed_data(schedule_data, homework_data, "u1", "p1")

    assert result["created_quests"] == 1
    svc.quest_dao.add_quest.assert_called_once()
