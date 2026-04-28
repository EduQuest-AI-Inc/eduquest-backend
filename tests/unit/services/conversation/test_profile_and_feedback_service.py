import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from services.conversation.profile_service import (
    ProfileConversationService,
    initiate_profile_conversation,
    continue_profile_conversation,
)
from services.conversation.teacher_feedback_service import (
    TeacherFeedbackConversationService,
    initiate_teacher_feedback,
    continue_teacher_feedback,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_runner_result(response_obj, last_response_id="rid1"):
    result = MagicMock()
    result.final_output = response_obj
    result.last_response_id = last_response_id
    return result


def _make_profile_response(response_text="Hello", profile=None):
    r = MagicMock()
    r.response = response_text
    r.profile = profile
    return r


def _make_full_profile():
    p = MagicMock()
    p.strengths = ["math"]
    p.weaknesses = ["writing"]
    p.interests = ["science"]
    p.learning_styles = ["visual"]
    return p


def _profile_svc(previous_response_id=None):
    svc = ProfileConversationService.__new__(ProfileConversationService)
    svc.agent = MagicMock()
    svc.previous_response_id = previous_response_id
    svc._runner = MagicMock()
    return svc


def _feedback_svc():
    svc = TeacherFeedbackConversationService.__new__(TeacherFeedbackConversationService)
    svc.agent = MagicMock()
    svc._runner = MagicMock()
    svc.session = MagicMock()
    return svc


# ── ProfileConversationService ────────────────────────────────────────────────

@pytest.mark.unit
def test_check_profile_all_fields_present():
    profile = _make_full_profile()
    response = _make_profile_response(profile=profile)
    result = ProfileConversationService._check_profile(response)
    assert result[0] is True
    assert set(result[1].keys()) == {"strength", "weakness", "interest", "learning_style"}
    assert result[1]["strength"] == ["math"]


@pytest.mark.unit
def test_check_profile_missing_strengths():
    p = MagicMock()
    p.strengths = []
    p.weaknesses = ["writing"]
    p.interests = ["science"]
    p.learning_styles = ["visual"]
    response = _make_profile_response(profile=p)
    assert ProfileConversationService._check_profile(response) == (False, None)


@pytest.mark.unit
def test_check_profile_missing_weaknesses():
    p = MagicMock()
    p.strengths = ["math"]
    p.weaknesses = []
    p.interests = ["science"]
    p.learning_styles = ["visual"]
    response = _make_profile_response(profile=p)
    assert ProfileConversationService._check_profile(response) == (False, None)


@pytest.mark.unit
def test_check_profile_missing_interests():
    p = MagicMock()
    p.strengths = ["math"]
    p.weaknesses = ["writing"]
    p.interests = []
    p.learning_styles = ["visual"]
    response = _make_profile_response(profile=p)
    assert ProfileConversationService._check_profile(response) == (False, None)


@pytest.mark.unit
def test_check_profile_missing_learning_styles():
    p = MagicMock()
    p.strengths = ["math"]
    p.weaknesses = ["writing"]
    p.interests = ["science"]
    p.learning_styles = []
    response = _make_profile_response(profile=p)
    assert ProfileConversationService._check_profile(response) == (False, None)


@pytest.mark.unit
def test_check_profile_no_profile_attr():
    response = _make_profile_response(profile=None)
    assert ProfileConversationService._check_profile(response) == (False, None)


@pytest.mark.unit
def test_profile_initiate_happy_path():
    svc = _profile_svc()
    response = _make_profile_response("Welcome!")
    svc._runner.run = AsyncMock(return_value=_make_runner_result(response, "rid1"))
    result = asyncio.run(svc.initiate({"first_name": "Alice", "last_name": "Smith"}))
    assert result["response"] == "Welcome!"
    assert result["response_id"] == "rid1"
    assert result["profile_complete"] is False
    assert "profile" not in result
    call_message = svc._runner.run.call_args[0][1]
    assert "Alice" in call_message
    assert "Smith" in call_message


@pytest.mark.unit
def test_profile_initiate_with_complete_profile():
    svc = _profile_svc()
    response = _make_profile_response("Done!", profile=_make_full_profile())
    svc._runner.run = AsyncMock(return_value=_make_runner_result(response))
    result = asyncio.run(svc.initiate({"first_name": "Bob", "last_name": ""}))
    assert result["profile_complete"] is True
    assert "profile" in result
    assert result["profile"]["strength"] == ["math"]


@pytest.mark.unit
def test_profile_initiate_missing_name_uses_default():
    svc = _profile_svc()
    response = _make_profile_response("Hi")
    svc._runner.run = AsyncMock(return_value=_make_runner_result(response))
    asyncio.run(svc.initiate({}))
    call_message = svc._runner.run.call_args[0][1]
    assert "Student" in call_message


@pytest.mark.unit
def test_profile_continue_passes_previous_response_id():
    svc = _profile_svc(previous_response_id="rid-prev")
    response = _make_profile_response("Continuing")
    svc._runner.run = AsyncMock(return_value=_make_runner_result(response, "rid2"))
    result = asyncio.run(svc.continue_conversation("I like reading"))
    assert svc._runner.run.call_args[1]["previous_response_id"] == "rid-prev"
    assert "response_id" in result
    assert "response" in result
    assert "profile_complete" in result


@pytest.mark.unit
def test_profile_continue_no_previous_id():
    svc = _profile_svc(previous_response_id=None)
    response = _make_profile_response("Hello")
    svc._runner.run = AsyncMock(return_value=_make_runner_result(response))
    asyncio.run(svc.continue_conversation("Hi"))
    assert svc._runner.run.call_args[1]["previous_response_id"] is None


@pytest.mark.unit
def test_initiate_profile_conversation_sync_wrapper():
    with patch("services.conversation.profile_service.ProfileConversationService") as MockCls:
        with patch("services.conversation.profile_service.asyncio.run", return_value={"response": "Hi"}) as mock_run:
            MockCls.return_value.initiate = AsyncMock(return_value={"response": "Hi"})
            result = initiate_profile_conversation({"first_name": "Ana"})
    mock_run.assert_called_once()
    assert result == {"response": "Hi"}


@pytest.mark.unit
def test_continue_profile_conversation_sync_wrapper():
    with patch("services.conversation.profile_service.ProfileConversationService") as MockCls:
        with patch("services.conversation.profile_service.asyncio.run", return_value={"response": "Next"}) as mock_run:
            MockCls.return_value.continue_conversation = AsyncMock(return_value={"response": "Next"})
            continue_profile_conversation("rid-old", "my message")
    MockCls.assert_called_once_with("rid-old")
    mock_run.assert_called_once()


# ── TeacherFeedbackConversationService ────────────────────────────────────────

@pytest.mark.unit
def test_extract_conversation_id_from_getter_method():
    svc = _feedback_svc()
    svc.session._get_session_id = MagicMock(return_value="cid-abc")
    result = asyncio.run(svc._extract_conversation_id())
    assert result == "cid-abc"


@pytest.mark.unit
def test_extract_conversation_id_from_async_getter():
    svc = _feedback_svc()
    svc.session._get_session_id = AsyncMock(return_value="cid-async")
    result = asyncio.run(svc._extract_conversation_id())
    assert result == "cid-async"


@pytest.mark.unit
def test_extract_conversation_id_fallback_to_session_id_attr():
    svc = _feedback_svc()
    svc.session = MagicMock(spec=[])
    svc.session._session_id = "cid-attr"
    result = asyncio.run(svc._extract_conversation_id())
    assert result == "cid-attr"


@pytest.mark.unit
def test_extract_conversation_id_returns_none_when_no_id():
    svc = _feedback_svc()
    svc.session = MagicMock(spec=[])
    result = asyncio.run(svc._extract_conversation_id())
    assert result is None


@pytest.mark.unit
def test_feedback_initiate_happy_path():
    svc = _feedback_svc()
    tf_resp = MagicMock()
    tf_resp.response = "Here is my feedback"
    tf_resp.suggested_change = None
    svc._runner.run = AsyncMock(return_value=MagicMock(final_output=tf_resp))
    svc._extract_conversation_id = AsyncMock(return_value="cid-1")
    result = asyncio.run(svc.initiate({"first_name": "Alice", "last_name": "Smith"}, "quest json"))
    assert result["response"] == "Here is my feedback"
    assert result["conversation_id"] == "cid-1"
    assert "suggested_change" in result
    call_args = svc._runner.run.call_args
    assert call_args[0][0] is svc.agent
    assert "Alice Smith" in call_args[0][1]
    assert "quest json" in call_args[0][1]
    assert call_args[1]["session"] is svc.session


@pytest.mark.unit
def test_feedback_initiate_missing_name():
    svc = _feedback_svc()
    tf_resp = MagicMock()
    tf_resp.response = "feedback"
    tf_resp.suggested_change = None
    svc._runner.run = AsyncMock(return_value=MagicMock(final_output=tf_resp))
    svc._extract_conversation_id = AsyncMock(return_value=None)
    asyncio.run(svc.initiate({}, "summary"))
    call_message = svc._runner.run.call_args[0][1]
    assert "summary" in call_message


@pytest.mark.unit
def test_feedback_continue_happy_path():
    svc = _feedback_svc()
    tf_resp = MagicMock()
    tf_resp.response = "Updated"
    tf_resp.suggested_change = {"week": 3}
    svc._runner.run = AsyncMock(return_value=MagicMock(final_output=tf_resp))
    result = asyncio.run(svc.continue_conversation("Adjust week 3"))
    assert result["response"] == "Updated"
    assert result["suggested_change"] == {"week": 3}
    call_args = svc._runner.run.call_args
    assert call_args[0][0] is svc.agent
    assert call_args[0][1] == "Adjust week 3"
    assert call_args[1]["session"] is svc.session


@pytest.mark.unit
def test_feedback_continue_returns_no_conversation_id():
    svc = _feedback_svc()
    tf_resp = MagicMock()
    tf_resp.response = "Done"
    tf_resp.suggested_change = None
    svc._runner.run = AsyncMock(return_value=MagicMock(final_output=tf_resp))
    result = asyncio.run(svc.continue_conversation("Hi"))
    assert "conversation_id" not in result


@pytest.mark.unit
def test_initiate_teacher_feedback_sync_wrapper():
    with patch("services.conversation.teacher_feedback_service.TeacherFeedbackConversationService") as MockCls:
        with patch("services.conversation.teacher_feedback_service.asyncio.run", return_value={"response": "X"}) as mock_run:
            MockCls.return_value.initiate = AsyncMock(return_value={"response": "X"})
            initiate_teacher_feedback({"first_name": "Bob"}, "summary", conversation_id="cid-old")
    MockCls.assert_called_once_with("cid-old")
    mock_run.assert_called_once()


@pytest.mark.unit
def test_continue_teacher_feedback_sync_wrapper():
    with patch("services.conversation.teacher_feedback_service.TeacherFeedbackConversationService") as MockCls:
        with patch("services.conversation.teacher_feedback_service.asyncio.run", return_value={"response": "Y"}) as mock_run:
            MockCls.return_value.continue_conversation = AsyncMock(return_value={"response": "Y"})
            continue_teacher_feedback("cid-1", "Follow up message")
    MockCls.assert_called_once_with("cid-1")
    mock_run.assert_called_once()
