import pytest
from unittest.mock import MagicMock, patch, mock_open

from services.conversation.grading_service import (
    _read_submission_text,
    _build_grading_input,
    grade_student_submission,
)

_QUEST_DICT_RUBRIC = {
    "rubric": {"criteria": "content"},
    "skills": "Reading; Writing",
    "instructions": "Write an essay.",
}
_QUEST_JSON_RUBRIC = {
    "rubric": '{"criteria": "content"}',
    "skills": "Reading",
    "instructions": "Write.",
}
_QUEST_DESCRIPTION_FALLBACK = {
    "rubric": {},
    "skills": [],
    "description": "From description.",
}


def _mock_result(**kwargs):
    r = MagicMock()
    r.skill_mastery = kwargs.get("skill_mastery", {"Reading": 0.9})
    r.numerical_grade = kwargs.get("numerical_grade", 85)
    r.feedback = kwargs.get("feedback", "Good")
    r.homework_changes_recommended = kwargs.get("homework_changes_recommended", False)
    r.recommended_changes = kwargs.get("recommended_changes", [])
    return r


# ---------------------------------------------------------------------------
# _read_submission_text
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_read_submission_text_happy_path():
    with patch("builtins.open", mock_open(read_data="submission content")):
        result = _read_submission_text("/tmp/file.txt")
    assert result == "submission content"


@pytest.mark.unit
def test_read_submission_text_file_error():
    with patch("builtins.open", side_effect=OSError("no such file")):
        result = _read_submission_text("/nonexistent/path.txt")
    assert result.startswith("[Unable to read submission file:")
    assert "no such file" in result


# ---------------------------------------------------------------------------
# _build_grading_input
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_build_grading_input_dict_rubric_and_semicolon_skills():
    from services.conversation.grading_service import GradingInput
    _build_grading_input(_QUEST_DICT_RUBRIC, "my submission")
    call_kwargs = GradingInput.call_args[1]
    assert call_kwargs["rubric"] == {"criteria": "content"}
    assert call_kwargs["skills"] == ["Reading", "Writing"]
    assert call_kwargs["instructions"] == "Write an essay."
    assert call_kwargs["submission"] == "my submission"


@pytest.mark.unit
def test_build_grading_input_json_string_rubric():
    from services.conversation.grading_service import GradingInput
    _build_grading_input(_QUEST_JSON_RUBRIC, "text")
    call_kwargs = GradingInput.call_args[1]
    assert call_kwargs["rubric"] == {"criteria": "content"}


@pytest.mark.unit
def test_build_grading_input_invalid_json_rubric():
    from services.conversation.grading_service import GradingInput
    quest = {**_QUEST_DICT_RUBRIC, "rubric": "not json{{"}
    _build_grading_input(quest, "text")
    call_kwargs = GradingInput.call_args[1]
    assert call_kwargs["rubric"] == {"raw": "not json{{"}


@pytest.mark.unit
def test_build_grading_input_skills_as_list():
    from services.conversation.grading_service import GradingInput
    quest = {**_QUEST_DICT_RUBRIC, "skills": ["Math", "Science"]}
    _build_grading_input(quest, "text")
    call_kwargs = GradingInput.call_args[1]
    assert call_kwargs["skills"] == ["Math", "Science"]


@pytest.mark.unit
def test_build_grading_input_empty_skills_string():
    from services.conversation.grading_service import GradingInput
    quest = {**_QUEST_DICT_RUBRIC, "skills": ""}
    _build_grading_input(quest, "text")
    call_kwargs = GradingInput.call_args[1]
    assert call_kwargs["skills"] == []


@pytest.mark.unit
def test_build_grading_input_instructions_fallback_to_description():
    from services.conversation.grading_service import GradingInput
    _build_grading_input(_QUEST_DESCRIPTION_FALLBACK, "text")
    call_kwargs = GradingInput.call_args[1]
    assert call_kwargs["instructions"] == "From description."


# ---------------------------------------------------------------------------
# grade_student_submission
# ---------------------------------------------------------------------------

@pytest.mark.unit
@patch("services.conversation.grading_service.asyncio.run")
def test_grade_student_submission_with_text(mock_run):
    ret = _mock_result()
    mock_run.side_effect = lambda coro: (coro.close(), ret)[1]
    result = grade_student_submission(_QUEST_DICT_RUBRIC, submission_text="my text")
    mock_run.assert_called_once()
    assert set(result.keys()) >= {"grade", "overall_score", "feedback", "change", "recommended_change", "response"}
    assert result["overall_score"] == 85
    assert result["feedback"] == "Good"
    assert result["change"] is False
    assert result["recommended_change"] is None
    assert "85" in result["response"]
    assert "Good" in result["response"]


@pytest.mark.unit
@patch("services.conversation.grading_service.asyncio.run")
@patch("services.conversation.grading_service._read_submission_text", return_value="file content")
def test_grade_student_submission_with_path(mock_read, mock_run):
    ret = _mock_result()
    mock_run.side_effect = lambda coro: (coro.close(), ret)[1]
    grade_student_submission(_QUEST_DICT_RUBRIC, submission_path="/tmp/file.txt")
    mock_read.assert_called_once_with("/tmp/file.txt")
    mock_run.assert_called_once()


@pytest.mark.unit
def test_grade_student_submission_neither_arg_raises():
    with pytest.raises(ValueError, match="submission_path or submission_text"):
        grade_student_submission(_QUEST_DICT_RUBRIC)


@pytest.mark.unit
@patch("services.conversation.grading_service.asyncio.run")
def test_grade_student_submission_recommended_changes_joined(mock_run):
    ret = _mock_result(recommended_changes=["Fix intro", "Add citations"])
    mock_run.side_effect = lambda coro: (coro.close(), ret)[1]
    result = grade_student_submission(_QUEST_DICT_RUBRIC, submission_text="x")
    assert result["recommended_change"] == "Fix intro; Add citations"


@pytest.mark.unit
@patch("services.conversation.grading_service.asyncio.run")
def test_grade_student_submission_empty_recommended_changes_is_none(mock_run):
    ret = _mock_result(recommended_changes=[])
    mock_run.side_effect = lambda coro: (coro.close(), ret)[1]
    result = grade_student_submission(_QUEST_DICT_RUBRIC, submission_text="x")
    assert result["recommended_change"] is None
