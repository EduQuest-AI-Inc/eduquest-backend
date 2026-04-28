import pytest
from unittest.mock import MagicMock

from services.quest.quest_creation_service import QuestCreationService


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


def _creation_svc():
    svc = QuestCreationService.__new__(QuestCreationService)
    svc.quest_dao = MagicMock()
    return svc


@pytest.mark.unit
def test_save_quests_from_schedule_creates_correct_count():
    svc = _creation_svc()
    result = svc.save_quests_from_schedule(SCHEDULE_1, "u1", "p1")
    assert result["created_quest_count"] == 2
    assert result["message"] == "Successfully created 2 quests"
    assert len(result["quest_ids"]) == 2
    assert svc.quest_dao.add_quest.call_count == 2


@pytest.mark.unit
def test_save_quests_from_schedule_quest_fields_correct():
    svc = _creation_svc()
    svc.save_quests_from_schedule(SCHEDULE_1, "u1", "p1")
    quest = svc.quest_dao.add_quest.call_args_list[0][0][0]
    assert quest.user_id == "u1"
    assert quest.period_id == "p1"
    assert quest.description == "Quest 1"
    assert quest.skills == "algebra"
    assert quest.week == 1
    assert quest.instructions == ""
    assert quest.rubric == {}
    assert quest.status == "not_started"
    assert isinstance(quest.quest_id, str) and quest.quest_id


@pytest.mark.unit
def test_save_quests_from_schedule_each_quest_has_unique_id():
    svc = _creation_svc()
    svc.save_quests_from_schedule(SCHEDULE_1, "u1", "p1")
    id1 = svc.quest_dao.add_quest.call_args_list[0][0][0].quest_id
    id2 = svc.quest_dao.add_quest.call_args_list[1][0][0].quest_id
    assert id1 != id2


@pytest.mark.unit
def test_save_quests_from_schedule_empty_list():
    svc = _creation_svc()
    result = svc.save_quests_from_schedule({"list_of_quests": []}, "u1", "p1")
    assert result["created_quest_count"] == 0
    assert result["quest_ids"] == []
    svc.quest_dao.add_quest.assert_not_called()


@pytest.mark.unit
def test_save_quests_from_schedule_missing_list_key():
    svc = _creation_svc()
    result = svc.save_quests_from_schedule({}, "u1", "p1")
    assert result["created_quest_count"] == 0


@pytest.mark.unit
def test_save_quests_from_schedule_quest_ids_in_result():
    svc = _creation_svc()
    result = svc.save_quests_from_schedule(SCHEDULE_1, "u1", "p1")
    quests = [call[0][0] for call in svc.quest_dao.add_quest.call_args_list]
    assert result["quest_ids"] == [q.quest_id for q in quests]


@pytest.mark.unit
def test_create_quests_from_homework_creates_correct_count():
    svc = _creation_svc()
    result = svc.create_quests_from_homework(HOMEWORK_1, "u1", "p1")
    assert result["created_quest_count"] == 1
    assert svc.quest_dao.add_quest.call_count == 1


@pytest.mark.unit
def test_create_quests_from_homework_quest_fields_correct():
    svc = _creation_svc()
    svc.create_quests_from_homework(HOMEWORK_1, "u1", "p1")
    quest = svc.quest_dao.add_quest.call_args_list[0][0][0]
    assert quest.instructions == "Read chapter 3"
    assert quest.rubric == {"criteria": "accuracy"}
    assert quest.description == "Quest A"
    assert quest.skills == "reading"
    assert quest.week == 1
    assert quest.status == "not_started"


@pytest.mark.unit
def test_create_quests_from_homework_empty_list():
    svc = _creation_svc()
    result = svc.create_quests_from_homework({"list_of_quests": []}, "u1", "p1")
    assert result["created_quest_count"] == 0
    svc.quest_dao.add_quest.assert_not_called()


@pytest.mark.unit
def test_create_quests_from_homework_missing_optional_fields():
    svc = _creation_svc()
    data = {"list_of_quests": [{"Name": "Q", "Skills": "s", "Week": 1}]}
    svc.create_quests_from_homework(data, "u1", "p1")
    quest = svc.quest_dao.add_quest.call_args_list[0][0][0]
    assert quest.instructions == ""
    assert quest.rubric == {}
