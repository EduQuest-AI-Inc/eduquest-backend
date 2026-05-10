import pytest
from unittest.mock import MagicMock

_QUEST_DICT_RUBRIC = {
    "rubric": {"criteria": "content"},
    "skills": "Reading; Writing",
    "instructions": "Write an essay.",
}


# ---------------------------------------------------------------------------
# BotProvider._build_grading_input
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_build_grading_input_dict_rubric_and_semicolon_skills():
    from bots.provider import BotProvider
    result = BotProvider._build_grading_input(_QUEST_DICT_RUBRIC, "my submission")
    assert result.rubric == {"criteria": "content"}
    assert result.skills == ["Reading", "Writing"]
    assert result.instructions == "Write an essay."
    assert result.submission == "my submission"


@pytest.mark.unit
def test_build_grading_input_json_string_rubric():
    from bots.provider import BotProvider
    quest = {**_QUEST_DICT_RUBRIC, "rubric": '{"criteria": "content"}'}
    result = BotProvider._build_grading_input(quest, "text")
    assert result.rubric == {"criteria": "content"}


@pytest.mark.unit
def test_build_grading_input_invalid_json_rubric():
    from bots.provider import BotProvider
    quest = {**_QUEST_DICT_RUBRIC, "rubric": "not json{{"}
    result = BotProvider._build_grading_input(quest, "text")
    assert result.rubric == {"raw": "not json{{"}


@pytest.mark.unit
def test_build_grading_input_skills_as_list():
    from bots.provider import BotProvider
    quest = {**_QUEST_DICT_RUBRIC, "skills": ["Math", "Science"]}
    result = BotProvider._build_grading_input(quest, "text")
    assert result.skills == ["Math", "Science"]


@pytest.mark.unit
def test_build_grading_input_empty_skills_string():
    from bots.provider import BotProvider
    quest = {**_QUEST_DICT_RUBRIC, "skills": ""}
    result = BotProvider._build_grading_input(quest, "text")
    assert result.skills == []


@pytest.mark.unit
def test_build_grading_input_instructions_fallback_to_description():
    from bots.provider import BotProvider
    quest = {"rubric": {}, "skills": [], "description": "From description."}
    result = BotProvider._build_grading_input(quest, "text")
    assert result.instructions == "From description."


# ---------------------------------------------------------------------------
# BotProvider._format_grading_result
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_format_grading_result_no_changes():
    from bots.provider import BotProvider
    r = MagicMock()
    r.skill_mastery = {"Reading": 0.9}
    r.numerical_grade = 85
    r.feedback = "Good"
    r.homework_changes_recommended = False
    r.recommended_changes = []
    result = BotProvider._format_grading_result(r)
    assert result["overall_score"] == 85
    assert result["grade"] == {"Reading": 0.9}
    assert result["feedback"] == "Good"
    assert result["change"] is False
    assert result["recommended_change"] is None
    assert "85" in result["response"]
    assert "Good" in result["response"]


@pytest.mark.unit
def test_format_grading_result_joins_changes():
    from bots.provider import BotProvider
    r = MagicMock()
    r.skill_mastery = {}
    r.numerical_grade = 70
    r.feedback = "Needs work"
    r.homework_changes_recommended = True
    r.recommended_changes = ["Fix intro", "Add citations"]
    result = BotProvider._format_grading_result(r)
    assert result["recommended_change"] == "Fix intro; Add citations"
    assert result["change"] is True
