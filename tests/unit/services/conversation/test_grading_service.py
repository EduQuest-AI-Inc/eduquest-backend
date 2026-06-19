import pytest
from unittest.mock import MagicMock, AsyncMock, patch, mock_open  # patch still used for _read_submission_text

from exceptions.validation_error import ValidationError
from services.conversation.grading_service import (
    _read_submission_text,
    grade_student_submission,
)

_QUEST_DICT_RUBRIC = {
    "rubric": {"criteria": "content"},
    "skills": "Reading; Writing",
    "instructions": "Write an essay.",
}

_EXPECTED_RESULT = {
    "grade": {"Reading": 0.9},
    "overall_score": 85,
    "feedback": "Good",
    "change": False,
    "recommended_change": None,
    "response": "Grade: 85\nFeedback: Good\nChanges recommended: False",
}


def _mock_provider(return_value=None):
    p = MagicMock()
    p.grade_submission = AsyncMock(return_value=return_value or _EXPECTED_RESULT)
    return p


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


@pytest.mark.unit
def test_read_submission_text_pdf_happy_path(tmp_path):
    mock_page = MagicMock()
    mock_page.extract_text.return_value = "Hello, world!"
    mock_reader = MagicMock()
    mock_reader.is_encrypted = False
    mock_reader.pages = [mock_page]
    with patch("services.conversation.grading_service.PdfReader", return_value=mock_reader):
        result = _read_submission_text(str(tmp_path / "essay.pdf"))
    assert result == "Hello, world!"


@pytest.mark.unit
def test_read_submission_text_pdf_encrypted():
    mock_reader = MagicMock()
    mock_reader.is_encrypted = True
    with patch("services.conversation.grading_service.PdfReader", return_value=mock_reader):
        result = _read_submission_text("/tmp/locked.pdf")
    assert "password-protected" in result


@pytest.mark.unit
def test_read_submission_text_pdf_no_text():
    mock_page = MagicMock()
    mock_page.extract_text.return_value = None
    mock_reader = MagicMock()
    mock_reader.is_encrypted = False
    mock_reader.pages = [mock_page]
    with patch("services.conversation.grading_service.PdfReader", return_value=mock_reader):
        result = _read_submission_text("/tmp/scanned.pdf")
    assert "no extractable text" in result


@pytest.mark.unit
def test_read_submission_text_pdf_corrupted():
    from pypdf.errors import PdfReadError
    with patch("services.conversation.grading_service.PdfReader", side_effect=PdfReadError("bad xref")):
        result = _read_submission_text("/tmp/corrupted.pdf")
    assert "Corrupted" in result


@pytest.mark.unit
def test_read_submission_text_pdf_partial_page_failure():
    good_page = MagicMock()
    good_page.extract_text.return_value = "Good content"
    bad_page = MagicMock()
    bad_page.extract_text.side_effect = Exception("decode error")
    mock_reader = MagicMock()
    mock_reader.is_encrypted = False
    mock_reader.pages = [good_page, bad_page]
    with patch("services.conversation.grading_service.PdfReader", return_value=mock_reader):
        result = _read_submission_text("/tmp/partial.pdf")
    assert "Good content" in result
    assert "unreadable" in result


@pytest.mark.unit
def test_read_submission_text_pdf_case_insensitive():
    mock_reader = MagicMock()
    mock_reader.is_encrypted = True
    with patch("services.conversation.grading_service.PdfReader", return_value=mock_reader):
        result = _read_submission_text("/tmp/upload.PDF")
    assert "password-protected" in result


# ---------------------------------------------------------------------------
# grade_student_submission
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_grade_student_submission_with_text():
    provider = _mock_provider()
    result = grade_student_submission(_QUEST_DICT_RUBRIC, submission_text="my text", bot_provider=provider)
    provider.grade_submission.assert_called_once_with(_QUEST_DICT_RUBRIC, "my text")
    assert set(result.keys()) >= {"grade", "overall_score", "feedback", "change", "recommended_change", "response"}
    assert result["overall_score"] == 85
    assert result["feedback"] == "Good"
    assert result["change"] is False
    assert result["recommended_change"] is None
    assert "85" in result["response"]


@pytest.mark.unit
def test_grade_student_submission_with_path():
    provider = _mock_provider()
    with patch("services.conversation.grading_service._read_submission_text", return_value="file content") as mock_read:
        grade_student_submission(_QUEST_DICT_RUBRIC, submission_path="/tmp/file.txt", bot_provider=provider)
    mock_read.assert_called_once_with("/tmp/file.txt")
    provider.grade_submission.assert_called_once_with(_QUEST_DICT_RUBRIC, "file content")


@pytest.mark.unit
def test_grade_student_submission_neither_arg_raises():
    provider = _mock_provider()
    with pytest.raises(ValidationError, match="submission_path or submission_text"):
        grade_student_submission(_QUEST_DICT_RUBRIC, bot_provider=provider)


@pytest.mark.unit
def test_grade_student_submission_recommended_changes_joined():
    result_with_changes = {**_EXPECTED_RESULT, "recommended_change": "Fix intro; Add citations"}
    provider = _mock_provider(return_value=result_with_changes)
    result = grade_student_submission(_QUEST_DICT_RUBRIC, submission_text="x", bot_provider=provider)
    assert result["recommended_change"] == "Fix intro; Add citations"


@pytest.mark.unit
def test_grade_student_submission_empty_recommended_changes_is_none():
    provider = _mock_provider()
    result = grade_student_submission(_QUEST_DICT_RUBRIC, submission_text="x", bot_provider=provider)
    assert result["recommended_change"] is None
