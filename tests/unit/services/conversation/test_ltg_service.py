import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from services.conversation.ltg_service import (
    LTGConversationService,
    run_initiate_ltg,
    run_continue_ltg,
)
from exceptions.validation_error import ValidationError
from exceptions.not_found_error import NotFoundError


def _svc(previous_response_id=None):
    svc = LTGConversationService.__new__(LTGConversationService)
    svc.agent = MagicMock()
    svc._runner = MagicMock()
    svc.previous_response_id = previous_response_id
    return svc


def _ltg_result(response_id="resp-1", message="Hello!", goal_1="G1",
                goal_2="G2", goal_3="G3", chosen_goal=None):
    r = MagicMock()
    r.last_response_id = response_id
    r.final_output.message = message
    r.final_output.goal_1 = goal_1
    r.final_output.goal_2 = goal_2
    r.final_output.goal_3 = goal_3
    r.final_output.chosen_goal = chosen_goal
    return r


_STUDENT = {
    "first_name": "Alice",
    "last_name": "Smith",
    "grade": "10",
    "strength": ["math"],
    "weakness": ["writing"],
    "interest": ["science"],
    "learning_style": ["visual"],
}


# ---------------------------------------------------------------------------
# _format_list_field
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_format_list_field_list_with_items():
    assert LTGConversationService._format_list_field(["Math", "Science"]) == "Math, Science"


@pytest.mark.unit
def test_format_list_field_empty_list():
    assert LTGConversationService._format_list_field([]) == "not specified"


@pytest.mark.unit
def test_format_list_field_truthy_string():
    assert LTGConversationService._format_list_field("visual learner") == "visual learner"


@pytest.mark.unit
def test_format_list_field_falsy_non_list():
    assert LTGConversationService._format_list_field(None) == "not specified"
    assert LTGConversationService._format_list_field("") == "not specified"


# ---------------------------------------------------------------------------
# LTGConversationService.initiate
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_initiate_happy_path():
    svc = _svc()
    svc._runner.run = AsyncMock(return_value=_ltg_result())
    result = asyncio.run(svc.initiate(_STUDENT))
    assert result["response_id"] == "resp-1"
    assert result["message"] == "Hello!"
    assert result["goal_1"] == "G1"
    assert result["goal_2"] == "G2"
    assert result["goal_3"] == "G3"
    assert result["chosen_goal"] is None
    svc._runner.run.assert_called_once()


@pytest.mark.unit
def test_initiate_message_includes_name_and_grade():
    svc = _svc()
    svc._runner.run = AsyncMock(return_value=_ltg_result())
    asyncio.run(svc.initiate(_STUDENT))
    call_args = svc._runner.run.call_args
    message_arg = call_args[0][1]
    assert "Alice Smith" in message_arg
    assert "10th grade" in message_arg


@pytest.mark.unit
def test_initiate_no_grade_skips_grade_fragment():
    svc = _svc()
    svc._runner.run = AsyncMock(return_value=_ltg_result())
    student = {**_STUDENT, "grade": ""}
    asyncio.run(svc.initiate(student))
    message_arg = svc._runner.run.call_args[0][1]
    assert "th grade" not in message_arg


# ---------------------------------------------------------------------------
# LTGConversationService.continue_conversation
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_continue_conversation_no_goal_chosen():
    svc = _svc()
    svc._runner.run = AsyncMock(return_value=_ltg_result(chosen_goal=None))
    result = asyncio.run(svc.continue_conversation("Tell me more"))
    assert result["goal_chosen"] is False
    assert result["message"] == "Hello!"
    assert result["chosen_goal"] is None


@pytest.mark.unit
def test_continue_conversation_goal_chosen():
    svc = _svc(previous_response_id="prev-99")
    svc._runner.run = AsyncMock(return_value=_ltg_result(message="Ignore", chosen_goal="Master algebra"))
    result = asyncio.run(svc.continue_conversation("I pick goal 1"))
    assert result["goal_chosen"] is True
    assert result["message"] == "Master algebra"
    assert result["chosen_goal"] == "Master algebra"
    call_kwargs = svc._runner.run.call_args[1]
    assert call_kwargs["previous_response_id"] == "prev-99"


@pytest.mark.unit
def test_continue_conversation_chosen_goal_literal_null():
    svc = _svc()
    svc._runner.run = AsyncMock(return_value=_ltg_result(chosen_goal="null"))
    result = asyncio.run(svc.continue_conversation("msg"))
    assert result["goal_chosen"] is False
    assert result["chosen_goal"] is None


@pytest.mark.unit
def test_continue_conversation_chosen_goal_literal_none():
    svc = _svc()
    svc._runner.run = AsyncMock(return_value=_ltg_result(chosen_goal="none"))
    result = asyncio.run(svc.continue_conversation("msg"))
    assert result["goal_chosen"] is False


# ---------------------------------------------------------------------------
# run_initiate_ltg
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_run_initiate_ltg_missing_period_id():
    with pytest.raises(ValidationError, match="Missing period ID"):
        run_initiate_ltg("u1", "")


@pytest.mark.unit
@patch("services.conversation.ltg_service.LtgConversationDAO")
@patch("services.conversation.ltg_service.StudentDAO")
@patch("services.conversation.ltg_service.PeriodDAO")
def test_run_initiate_ltg_student_not_found(mock_period_cls, mock_student_cls, mock_ltg_cls):
    mock_student_cls.return_value.get_student_by_id.return_value = None
    with pytest.raises(Exception, match="Student not found"):
        run_initiate_ltg("u1", "p1")


@pytest.mark.unit
@patch("services.conversation.ltg_service.LtgConversationDAO")
@patch("services.conversation.ltg_service.StudentDAO")
@patch("services.conversation.ltg_service.PeriodDAO")
def test_run_initiate_ltg_period_not_found(mock_period_cls, mock_student_cls, mock_ltg_cls):
    mock_student_cls.return_value.get_student_by_id.return_value = {"user_id": "u1"}
    mock_period_cls.return_value.get_period_by_id.return_value = None
    with pytest.raises(NotFoundError):
        run_initiate_ltg("u1", "p1")


@pytest.mark.unit
@patch("services.conversation.ltg_service.LtgConversationDAO")
@patch("services.conversation.ltg_service.StudentDAO")
@patch("services.conversation.ltg_service.PeriodDAO")
def test_run_initiate_ltg_no_vector_store(mock_period_cls, mock_student_cls, mock_ltg_cls):
    mock_student_cls.return_value.get_student_by_id.return_value = {"user_id": "u1"}
    mock_period_cls.return_value.get_period_by_id.return_value = {"vector_store_id": None}
    with pytest.raises(Exception, match="vector store"):
        run_initiate_ltg("u1", "p1")


@pytest.mark.unit
@patch("services.conversation.ltg_service.initiate_ltg_conversation")
@patch("services.conversation.ltg_service.LtgConversationDAO")
@patch("services.conversation.ltg_service.StudentDAO")
@patch("services.conversation.ltg_service.PeriodDAO")
def test_run_initiate_ltg_existing_conversation_returns_resumed(
    mock_period_cls, mock_student_cls, mock_ltg_cls, mock_initiate
):
    mock_student_cls.return_value.get_student_by_id.return_value = {"user_id": "u1"}
    mock_period_cls.return_value.get_period_by_id.return_value = {"vector_store_id": "vs-1"}
    mock_ltg_cls.return_value.get_conversation_id.return_value = "conv-existing"
    result = run_initiate_ltg("u1", "p1")
    assert result["resumed"] is True
    assert result["conversation_id"] == "conv-existing"
    mock_initiate.assert_not_called()


@pytest.mark.unit
@patch("services.conversation.ltg_service.initiate_ltg_conversation",
       return_value={"response_id": "resp-new", "message": "Goals!", "goal_1": "G1", "goal_2": "G2", "goal_3": "G3"})
@patch("services.conversation.ltg_service.LtgConversationDAO")
@patch("services.conversation.ltg_service.StudentDAO")
@patch("services.conversation.ltg_service.PeriodDAO")
def test_run_initiate_ltg_new_conversation(mock_period_cls, mock_student_cls, mock_ltg_cls, mock_initiate):
    mock_student_cls.return_value.get_student_by_id.return_value = {
        "user_id": "u1", "first_name": "A", "last_name": "B", "grade": "",
        "strength": [], "weakness": [], "interest": [], "learning_style": [],
    }
    mock_period_cls.return_value.get_period_by_id.return_value = {"vector_store_id": "vs-1"}
    mock_ltg_cls.return_value.get_conversation_id.return_value = None
    result = run_initiate_ltg("u1", "p1")
    assert result["resumed"] is False
    assert "conversation_id" in result
    assert result["response"]["goal_1"] == "G1"
    mock_ltg_cls.return_value.upsert_conversation.assert_called_once()
    call = mock_ltg_cls.return_value.upsert_conversation.call_args
    assert call[0][0] == "u1"
    assert call[0][1] == "p1"
    assert call[1]["last_response_id"] == "resp-new"


@pytest.mark.unit
@patch("services.conversation.ltg_service.initiate_ltg_conversation", return_value={"message": "x"})
@patch("services.conversation.ltg_service.LtgConversationDAO")
@patch("services.conversation.ltg_service.StudentDAO")
@patch("services.conversation.ltg_service.PeriodDAO")
def test_run_initiate_ltg_no_response_id_raises(mock_period_cls, mock_student_cls, mock_ltg_cls, mock_initiate):
    mock_student_cls.return_value.get_student_by_id.return_value = {
        "user_id": "u1", "first_name": "A", "last_name": "B", "grade": "",
        "strength": [], "weakness": [], "interest": [], "learning_style": [],
    }
    mock_period_cls.return_value.get_period_by_id.return_value = {"vector_store_id": "vs-1"}
    mock_ltg_cls.return_value.get_conversation_id.return_value = None
    with pytest.raises(Exception, match="no response_id"):
        run_initiate_ltg("u1", "p1")


# ---------------------------------------------------------------------------
# run_continue_ltg
# ---------------------------------------------------------------------------

@pytest.mark.unit
@patch("services.conversation.ltg_service.continue_ltg_conversation",
       return_value={"response_id": "r1", "message": "ok", "goal_chosen": False, "chosen_goal": None})
@patch("services.conversation.ltg_service.StudentLongTermGoalDAO")
@patch("services.conversation.ltg_service.LtgConversationDAO")
@patch("services.conversation.ltg_service.PeriodDAO")
def test_run_continue_ltg_resolves_period_via_find(mock_period_cls, mock_ltg_cls, mock_goal_cls, mock_cont):
    mock_ltg_cls.return_value.find_period_for_conversation.return_value = "p1"
    mock_period_cls.return_value.get_period_by_id.return_value = {"vector_store_id": "vs-1"}
    mock_ltg_cls.return_value.get_last_response_id.return_value = None
    run_continue_ltg("u1", "ltg", "conv-1", "hi")
    mock_ltg_cls.return_value.find_period_for_conversation.assert_called_once_with("u1", "conv-1")


@pytest.mark.unit
@patch("services.conversation.ltg_service.LtgConversationDAO")
@patch("services.conversation.ltg_service.PeriodDAO")
def test_run_continue_ltg_no_period_raises(mock_period_cls, mock_ltg_cls):
    mock_ltg_cls.return_value.find_period_for_conversation.return_value = None
    with pytest.raises(Exception, match="Could not determine period"):
        run_continue_ltg("u1", "ltg", "conv-1", "hi")


@pytest.mark.unit
@patch("services.conversation.ltg_service.LtgConversationDAO")
@patch("services.conversation.ltg_service.PeriodDAO")
def test_run_continue_ltg_period_not_found_raises(mock_period_cls, mock_ltg_cls):
    mock_period_cls.return_value.get_period_by_id.return_value = None
    with pytest.raises(Exception, match="Period not found"):
        run_continue_ltg("u1", "ltg", "conv-1", "hi", period_id="p1")


@pytest.mark.unit
@patch("services.conversation.ltg_service.LtgConversationDAO")
@patch("services.conversation.ltg_service.PeriodDAO")
def test_run_continue_ltg_no_vector_store_raises(mock_period_cls, mock_ltg_cls):
    mock_period_cls.return_value.get_period_by_id.return_value = {"vector_store_id": None}
    with pytest.raises(Exception, match="vector store"):
        run_continue_ltg("u1", "ltg", "conv-1", "hi", period_id="p1")


@pytest.mark.unit
@patch("services.conversation.ltg_service.continue_ltg_conversation",
       return_value={"response_id": "r2", "message": "Continue!", "goal_chosen": False, "chosen_goal": None})
@patch("services.conversation.ltg_service.StudentLongTermGoalDAO")
@patch("services.conversation.ltg_service.LtgConversationDAO")
@patch("services.conversation.ltg_service.PeriodDAO")
def test_run_continue_ltg_happy_path_no_goal(mock_period_cls, mock_ltg_cls, mock_goal_cls, mock_cont):
    mock_period_cls.return_value.get_period_by_id.return_value = {"vector_store_id": "vs-1"}
    mock_ltg_cls.return_value.get_last_response_id.return_value = "prev-r"
    result = run_continue_ltg("u1", "ltg", "conv-1", "hi", period_id="p1")
    assert result == {"response": "Continue!", "goal_chosen": False}
    mock_ltg_cls.return_value.update_last_response_id.assert_called_once_with("u1", "p1", "r2")
    mock_goal_cls.return_value.upsert.assert_not_called()


@pytest.mark.unit
@patch("services.conversation.ltg_service.continue_ltg_conversation",
       return_value={"response_id": "r3", "message": "Goal set!", "goal_chosen": True, "chosen_goal": "Master algebra"})
@patch("services.conversation.ltg_service.StudentLongTermGoalDAO")
@patch("services.conversation.ltg_service.LtgConversationDAO")
@patch("services.conversation.ltg_service.PeriodDAO")
def test_run_continue_ltg_goal_chosen_upserts(mock_period_cls, mock_ltg_cls, mock_goal_cls, mock_cont):
    mock_period_cls.return_value.get_period_by_id.return_value = {"vector_store_id": "vs-1"}
    mock_ltg_cls.return_value.get_last_response_id.return_value = None
    result = run_continue_ltg("u1", "ltg", "conv-1", "hi", period_id="p1")
    assert result["goal_chosen"] is True
    mock_goal_cls.return_value.upsert.assert_called_once_with("u1", "p1", "Master algebra")


@pytest.mark.unit
@patch("services.conversation.ltg_service.continue_ltg_conversation", side_effect=Exception("AI failure"))
@patch("services.conversation.ltg_service.StudentLongTermGoalDAO")
@patch("services.conversation.ltg_service.LtgConversationDAO")
@patch("services.conversation.ltg_service.PeriodDAO")
def test_run_continue_ltg_exception_returns_error_dict(mock_period_cls, mock_ltg_cls, mock_goal_cls, mock_cont):
    mock_period_cls.return_value.get_period_by_id.return_value = {"vector_store_id": "vs-1"}
    mock_ltg_cls.return_value.get_last_response_id.return_value = None
    result = run_continue_ltg("u1", "ltg", "conv-1", "hi", period_id="p1")
    assert result == {"error": "AI failure"}
