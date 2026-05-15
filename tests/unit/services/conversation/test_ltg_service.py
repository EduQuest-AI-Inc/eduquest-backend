import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from services.conversation.ltg_service import (
    LTGConversationService,
    LTGOrchestrationService,
)
from exceptions.validation_error import ValidationError
from exceptions.not_found_error import NotFoundError


def _svc(previous_response_id=None, mock_provider=None):
    svc = LTGConversationService.__new__(LTGConversationService)
    svc.agent = MagicMock()
    svc.previous_response_id = previous_response_id
    svc._bot_provider = mock_provider or MagicMock()
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
    mock_provider = MagicMock()
    mock_provider.run_conversation = AsyncMock(return_value=_ltg_result())
    svc = _svc(mock_provider=mock_provider)
    result = asyncio.run(svc.initiate(_STUDENT))
    assert result["response_id"] == "resp-1"
    assert result["message"] == "Hello!"
    assert result["goal_1"] == "G1"
    assert result["goal_2"] == "G2"
    assert result["goal_3"] == "G3"
    assert result["chosen_goal"] is None
    mock_provider.run_conversation.assert_called_once()
    call_kwargs = mock_provider.run_conversation.call_args[1]
    assert call_kwargs["trace_workflow_name"] == "ltg_conversation"
    assert call_kwargs["trace_metadata"]["conversation_type"] == "ltg"
    assert call_kwargs["trace_metadata"]["phase"] == "initiate"


@pytest.mark.unit
def test_initiate_message_includes_name_and_grade():
    mock_provider = MagicMock()
    mock_provider.run_conversation = AsyncMock(return_value=_ltg_result())
    svc = _svc(mock_provider=mock_provider)
    asyncio.run(svc.initiate(_STUDENT))
    message_arg = mock_provider.run_conversation.call_args[0][1]
    assert "Alice Smith" in message_arg
    assert "10th grade" in message_arg


@pytest.mark.unit
def test_initiate_no_grade_skips_grade_fragment():
    mock_provider = MagicMock()
    mock_provider.run_conversation = AsyncMock(return_value=_ltg_result())
    student = {**_STUDENT, "grade": ""}
    svc = _svc(mock_provider=mock_provider)
    asyncio.run(svc.initiate(student))
    message_arg = mock_provider.run_conversation.call_args[0][1]
    assert "th grade" not in message_arg


# ---------------------------------------------------------------------------
# LTGConversationService.continue_conversation
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_continue_conversation_no_goal_chosen():
    mock_provider = MagicMock()
    mock_provider.run_conversation = AsyncMock(return_value=_ltg_result(chosen_goal=None))
    svc = _svc(mock_provider=mock_provider)
    result = asyncio.run(svc.continue_conversation("Tell me more"))
    assert result["goal_chosen"] is False
    assert result["message"] == "Hello!"
    assert result["chosen_goal"] is None


@pytest.mark.unit
def test_continue_conversation_goal_chosen():
    mock_provider = MagicMock()
    mock_provider.run_conversation = AsyncMock(return_value=_ltg_result(message="Ignore", chosen_goal="Master algebra"))
    svc = _svc(previous_response_id="prev-99", mock_provider=mock_provider)
    result = asyncio.run(svc.continue_conversation("I pick goal 1"))
    assert result["goal_chosen"] is True
    assert result["message"] == "Master algebra"
    assert result["chosen_goal"] == "Master algebra"
    assert mock_provider.run_conversation.call_args[1]["previous_response_id"] == "prev-99"
    assert mock_provider.run_conversation.call_args[1]["trace_workflow_name"] == "ltg_conversation"
    assert mock_provider.run_conversation.call_args[1]["trace_group_id"] == "prev-99"
    assert mock_provider.run_conversation.call_args[1]["trace_metadata"]["phase"] == "continue"


@pytest.mark.unit
def test_continue_conversation_chosen_goal_literal_null():
    mock_provider = MagicMock()
    mock_provider.run_conversation = AsyncMock(return_value=_ltg_result(chosen_goal="null"))
    svc = _svc(mock_provider=mock_provider)
    result = asyncio.run(svc.continue_conversation("msg"))
    assert result["goal_chosen"] is False
    assert result["chosen_goal"] is None


@pytest.mark.unit
def test_continue_conversation_chosen_goal_literal_none():
    mock_provider = MagicMock()
    mock_provider.run_conversation = AsyncMock(return_value=_ltg_result(chosen_goal="none"))
    svc = _svc(mock_provider=mock_provider)
    result = asyncio.run(svc.continue_conversation("msg"))
    assert result["goal_chosen"] is False


# ---------------------------------------------------------------------------
# LTGOrchestrationService helpers
# ---------------------------------------------------------------------------

def _initiate_svc(student=None, period=None, conversation_id=None):
    student_dao = MagicMock()
    student_dao.get_student_by_id.return_value = student
    period_dao = MagicMock()
    period_dao.get_period_by_id.return_value = period
    ltg_dao = MagicMock()
    ltg_dao.get_conversation_id.return_value = conversation_id
    curriculum_svc = MagicMock()
    curriculum_svc.get_curriculum.return_value = {}
    return LTGOrchestrationService(
        period_dao=period_dao,
        student_dao=student_dao,
        ltg_conversation_dao=ltg_dao,
        curriculum_service=curriculum_svc,
        bot_provider=MagicMock(),
    )


def _continue_svc(period=None, conversation_period_id=None, last_response_id=None, goal_dao=None):
    period_dao = MagicMock()
    period_dao.get_period_by_id.return_value = period
    ltg_dao = MagicMock()
    ltg_dao.find_period_for_conversation.return_value = conversation_period_id
    ltg_dao.get_last_response_id.return_value = last_response_id
    return LTGOrchestrationService(
        period_dao=period_dao,
        ltg_conversation_dao=ltg_dao,
        student_long_term_goal_dao=goal_dao or MagicMock(),
        bot_provider=MagicMock(),
    )


# ---------------------------------------------------------------------------
# LTGOrchestrationService.initiate
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_run_initiate_ltg_missing_period_id():
    svc = _initiate_svc()
    with pytest.raises(ValidationError, match="Missing period ID"):
        svc.initiate("u1", "")


@pytest.mark.unit
def test_run_initiate_ltg_student_not_found():
    svc = _initiate_svc(student=None)
    with pytest.raises(Exception, match="Student not found"):
        svc.initiate("u1", "p1")


@pytest.mark.unit
def test_run_initiate_ltg_period_not_found():
    svc = _initiate_svc(student={"user_id": "u1"}, period=None)
    with pytest.raises(NotFoundError):
        svc.initiate("u1", "p1")


@pytest.mark.unit
def test_run_initiate_ltg_no_vector_store():
    svc = _initiate_svc(student={"user_id": "u1"}, period={"vector_store_id": None})
    with pytest.raises(Exception, match="vector store"):
        svc.initiate("u1", "p1")


@pytest.mark.unit
def test_run_initiate_ltg_existing_conversation_returns_resumed():
    svc = _initiate_svc(
        student={"user_id": "u1"},
        period={"vector_store_id": "vs-1"},
        conversation_id="conv-existing",
    )
    result = svc.initiate("u1", "p1")
    assert result["resumed"] is True
    assert result["conversation_id"] == "conv-existing"


@pytest.mark.unit
@patch("services.conversation.ltg_service.initiate_ltg_conversation",
       return_value={"response_id": "resp-new", "message": "Goals!", "goal_1": "G1", "goal_2": "G2", "goal_3": "G3"})
def test_run_initiate_ltg_new_conversation(mock_initiate):
    svc = _initiate_svc(
        student={"user_id": "u1", "first_name": "A", "last_name": "B", "grade": "",
                 "strength": [], "weakness": [], "interest": [], "learning_style": []},
        period={"vector_store_id": "vs-1"},
        conversation_id=None,
    )
    result = svc.initiate("u1", "p1")
    assert result["resumed"] is False
    assert "conversation_id" in result
    assert result["response"]["goal_1"] == "G1"
    svc.ltg_conversation_dao.upsert_conversation.assert_called_once()
    call = svc.ltg_conversation_dao.upsert_conversation.call_args
    assert call[0][0] == "u1"
    assert call[0][1] == "p1"
    assert call[1]["last_response_id"] == "resp-new"


@pytest.mark.unit
@patch("services.conversation.ltg_service.initiate_ltg_conversation", return_value={"message": "x"})
def test_run_initiate_ltg_no_response_id_raises(mock_initiate):
    svc = _initiate_svc(
        student={"user_id": "u1", "first_name": "A", "last_name": "B", "grade": "",
                 "strength": [], "weakness": [], "interest": [], "learning_style": []},
        period={"vector_store_id": "vs-1"},
        conversation_id=None,
    )
    with pytest.raises(Exception, match="no response_id"):
        svc.initiate("u1", "p1")


# ---------------------------------------------------------------------------
# LTGOrchestrationService.continue_conversation
# ---------------------------------------------------------------------------

@pytest.mark.unit
@patch("services.conversation.ltg_service.continue_ltg_conversation",
       return_value={"response_id": "r1", "message": "ok", "goal_chosen": False, "chosen_goal": None})
def test_run_continue_ltg_resolves_period_via_find(mock_cont):
    svc = _continue_svc(period={"vector_store_id": "vs-1"}, conversation_period_id="p1")
    svc.continue_conversation("u1", "ltg", "conv-1", "hi")
    svc.ltg_conversation_dao.find_period_for_conversation.assert_called_once_with("u1", "conv-1")


@pytest.mark.unit
def test_run_continue_ltg_no_period_raises():
    svc = _continue_svc(conversation_period_id=None)
    with pytest.raises(Exception, match="Could not determine period"):
        svc.continue_conversation("u1", "ltg", "conv-1", "hi")


@pytest.mark.unit
def test_run_continue_ltg_period_not_found_raises():
    svc = _continue_svc(period=None)
    with pytest.raises(Exception, match="Period not found"):
        svc.continue_conversation("u1", "ltg", "conv-1", "hi", period_id="p1")


@pytest.mark.unit
def test_run_continue_ltg_no_vector_store_raises():
    svc = _continue_svc(period={"vector_store_id": None})
    with pytest.raises(Exception, match="vector store"):
        svc.continue_conversation("u1", "ltg", "conv-1", "hi", period_id="p1")


@pytest.mark.unit
@patch("services.conversation.ltg_service.continue_ltg_conversation",
       return_value={"response_id": "r2", "message": "Continue!", "goal_chosen": False, "chosen_goal": None})
def test_run_continue_ltg_happy_path_no_goal(mock_cont):
    svc = _continue_svc(period={"vector_store_id": "vs-1"}, last_response_id="prev-r")
    result = svc.continue_conversation("u1", "ltg", "conv-1", "hi", period_id="p1")
    assert result == {"response": "Continue!", "goal_chosen": False}
    svc.ltg_conversation_dao.update_last_response_id.assert_called_once_with("u1", "p1", "r2")
    svc.student_long_term_goal_dao.upsert.assert_not_called()


@pytest.mark.unit
@patch("services.conversation.ltg_service.continue_ltg_conversation",
       return_value={"response_id": "r3", "message": "Goal set!", "goal_chosen": True, "chosen_goal": "Master algebra"})
def test_run_continue_ltg_goal_chosen_upserts(mock_cont):
    svc = _continue_svc(period={"vector_store_id": "vs-1"})
    result = svc.continue_conversation("u1", "ltg", "conv-1", "hi", period_id="p1")
    assert result["goal_chosen"] is True
    svc.student_long_term_goal_dao.upsert.assert_called_once_with("u1", "p1", "Master algebra")


@pytest.mark.unit
@patch("services.conversation.ltg_service.continue_ltg_conversation", side_effect=Exception("AI failure"))
def test_run_continue_ltg_exception_returns_error_dict(mock_cont):
    svc = _continue_svc(period={"vector_store_id": "vs-1"})
    result = svc.continue_conversation("u1", "ltg", "conv-1", "hi", period_id="p1")
    assert result == {"error": "AI failure"}
