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
    return svc


def _feedback_svc():
    svc = TeacherFeedbackConversationService.__new__(TeacherFeedbackConversationService)
    svc.agent = MagicMock()
    svc.session = MagicMock()
    return svc


# ── ProfileConversationService ────────────────────────────────────────────────

@pytest.mark.unit
def test_profile_initiate_complete_profile_sets_flag_and_profile_key():
    """initiate() with all profile fields populated → profile_complete=True and profile key present."""
    svc = _profile_svc()
    response = _make_profile_response("Welcome!", profile=_make_full_profile())
    mock_provider = MagicMock()
    mock_provider.run_conversation = AsyncMock(return_value=_make_runner_result(response))
    with patch("services.conversation.profile_service.get_bot_provider", return_value=mock_provider):
        result = asyncio.run(svc.initiate({"first_name": "Alice", "last_name": "Smith"}))
    assert result["profile_complete"] is True
    assert "profile" in result
    assert set(result["profile"].keys()) == {"strength", "weakness", "interest", "learning_style"}
    assert result["profile"]["strength"] == ["math"]


@pytest.mark.unit
def test_profile_initiate_missing_one_field_incomplete():
    """initiate() when any profile field is empty → profile_complete=False, no profile key."""
    svc = _profile_svc()
    p = MagicMock()
    p.strengths = []          # missing strengths
    p.weaknesses = ["writing"]
    p.interests = ["science"]
    p.learning_styles = ["visual"]
    response = _make_profile_response("Tell me more", profile=p)
    mock_provider = MagicMock()
    mock_provider.run_conversation = AsyncMock(return_value=_make_runner_result(response))
    with patch("services.conversation.profile_service.get_bot_provider", return_value=mock_provider):
        result = asyncio.run(svc.initiate({"first_name": "Alice", "last_name": "Smith"}))
    assert result["profile_complete"] is False
    assert "profile" not in result


@pytest.mark.unit
def test_profile_initiate_no_profile_incomplete():
    """initiate() when profile is None → profile_complete=False, no profile key."""
    svc = _profile_svc()
    response = _make_profile_response("Hello", profile=None)
    mock_provider = MagicMock()
    mock_provider.run_conversation = AsyncMock(return_value=_make_runner_result(response))
    with patch("services.conversation.profile_service.get_bot_provider", return_value=mock_provider):
        result = asyncio.run(svc.initiate({"first_name": "Bob", "last_name": ""}))
    assert result["profile_complete"] is False
    assert "profile" not in result


@pytest.mark.unit
def test_profile_continue_complete_profile_sets_flag_and_profile_key():
    """continue_conversation() with all profile fields populated → profile_complete=True and profile key present."""
    svc = _profile_svc(previous_response_id="rid-prev")
    response = _make_profile_response("Done!", profile=_make_full_profile())
    mock_provider = MagicMock()
    mock_provider.run_conversation = AsyncMock(return_value=_make_runner_result(response, "rid2"))
    with patch("services.conversation.profile_service.get_bot_provider", return_value=mock_provider):
        result = asyncio.run(svc.continue_conversation("I like reading"))
    assert result["profile_complete"] is True
    assert "profile" in result
    assert result["profile"]["weakness"] == ["writing"]


@pytest.mark.unit
def test_profile_continue_missing_profile_field_incomplete():
    """continue_conversation() when a profile field is missing → profile_complete=False, no profile key."""
    svc = _profile_svc(previous_response_id="rid-prev")
    p = MagicMock()
    p.strengths = ["math"]
    p.weaknesses = ["writing"]
    p.interests = ["science"]
    p.learning_styles = []    # missing learning styles
    response = _make_profile_response("Keep going", profile=p)
    mock_provider = MagicMock()
    mock_provider.run_conversation = AsyncMock(return_value=_make_runner_result(response, "rid3"))
    with patch("services.conversation.profile_service.get_bot_provider", return_value=mock_provider):
        result = asyncio.run(svc.continue_conversation("I prefer visual learning"))
    assert result["profile_complete"] is False
    assert "profile" not in result


@pytest.mark.unit
def test_profile_initiate_happy_path():
    svc = _profile_svc()
    response = _make_profile_response("Welcome!")
    mock_provider = MagicMock()
    mock_provider.run_conversation = AsyncMock(return_value=_make_runner_result(response, "rid1"))
    with patch("services.conversation.profile_service.get_bot_provider", return_value=mock_provider):
        result = asyncio.run(svc.initiate({"first_name": "Alice", "last_name": "Smith"}))
    assert result["response"] == "Welcome!"
    assert result["response_id"] == "rid1"
    assert result["profile_complete"] is False
    assert "profile" not in result
    call_message = mock_provider.run_conversation.call_args[0][1]
    assert "Alice" in call_message
    assert "Smith" in call_message


@pytest.mark.unit
def test_profile_initiate_with_complete_profile():
    svc = _profile_svc()
    response = _make_profile_response("Done!", profile=_make_full_profile())
    mock_provider = MagicMock()
    mock_provider.run_conversation = AsyncMock(return_value=_make_runner_result(response))
    with patch("services.conversation.profile_service.get_bot_provider", return_value=mock_provider):
        result = asyncio.run(svc.initiate({"first_name": "Bob", "last_name": ""}))
    assert result["profile_complete"] is True
    assert "profile" in result
    assert result["profile"]["strength"] == ["math"]


@pytest.mark.unit
def test_profile_initiate_missing_name_uses_default():
    svc = _profile_svc()
    response = _make_profile_response("Hi")
    mock_provider = MagicMock()
    mock_provider.run_conversation = AsyncMock(return_value=_make_runner_result(response))
    with patch("services.conversation.profile_service.get_bot_provider", return_value=mock_provider):
        asyncio.run(svc.initiate({}))
    call_message = mock_provider.run_conversation.call_args[0][1]
    assert "Student" in call_message


@pytest.mark.unit
def test_profile_continue_passes_previous_response_id():
    svc = _profile_svc(previous_response_id="rid-prev")
    response = _make_profile_response("Continuing")
    mock_provider = MagicMock()
    mock_provider.run_conversation = AsyncMock(return_value=_make_runner_result(response, "rid2"))
    with patch("services.conversation.profile_service.get_bot_provider", return_value=mock_provider):
        result = asyncio.run(svc.continue_conversation("I like reading"))
    assert mock_provider.run_conversation.call_args[1]["previous_response_id"] == "rid-prev"
    assert "response_id" in result
    assert "response" in result
    assert "profile_complete" in result


@pytest.mark.unit
def test_profile_continue_no_previous_id():
    svc = _profile_svc(previous_response_id=None)
    response = _make_profile_response("Hello")
    mock_provider = MagicMock()
    mock_provider.run_conversation = AsyncMock(return_value=_make_runner_result(response))
    with patch("services.conversation.profile_service.get_bot_provider", return_value=mock_provider):
        asyncio.run(svc.continue_conversation("Hi"))
    assert mock_provider.run_conversation.call_args[1]["previous_response_id"] is None


@pytest.mark.unit
def test_initiate_profile_conversation_sync_wrapper():
    with patch("services.conversation.profile_service.ProfileConversationService") as MockCls:
        with patch("services.conversation.profile_service.asyncio.run", return_value={"response": "Hi"}) as mock_run:
            MockCls.return_value.initiate = MagicMock(return_value={"response": "Hi"})
            result = initiate_profile_conversation({"first_name": "Ana"})
    mock_run.assert_called_once()
    assert result == {"response": "Hi"}


@pytest.mark.unit
def test_continue_profile_conversation_sync_wrapper():
    with patch("services.conversation.profile_service.ProfileConversationService") as MockCls:
        with patch("services.conversation.profile_service.asyncio.run", return_value={"response": "Next"}) as mock_run:
            MockCls.return_value.continue_conversation = MagicMock(return_value={"response": "Next"})
            continue_profile_conversation("rid-old", "my message")
    MockCls.assert_called_once_with("rid-old")
    mock_run.assert_called_once()


# ── TeacherFeedbackConversationService ────────────────────────────────────────

@pytest.mark.unit
def test_feedback_initiate_conversation_id_from_sync_getter():
    """initiate() resolves conversation_id via session._get_session_id() (sync callable)."""
    svc = _feedback_svc()
    svc.session._get_session_id = MagicMock(return_value="cid-sync")
    tf_resp = MagicMock()
    tf_resp.response = "feedback"
    tf_resp.suggested_change = None
    mock_provider = MagicMock()
    mock_provider.run_conversation = AsyncMock(return_value=MagicMock(final_output=tf_resp))
    with patch("services.conversation.teacher_feedback_service.get_bot_provider", return_value=mock_provider):
        result = asyncio.run(svc.initiate({"first_name": "Alice", "last_name": "Smith"}, "quest json"))
    assert result["conversation_id"] == "cid-sync"


@pytest.mark.unit
def test_feedback_initiate_conversation_id_from_async_getter():
    """initiate() resolves conversation_id via an async session._get_session_id() coroutine."""
    svc = _feedback_svc()
    svc.session._get_session_id = AsyncMock(return_value="cid-async")
    tf_resp = MagicMock()
    tf_resp.response = "feedback"
    tf_resp.suggested_change = None
    mock_provider = MagicMock()
    mock_provider.run_conversation = AsyncMock(return_value=MagicMock(final_output=tf_resp))
    with patch("services.conversation.teacher_feedback_service.get_bot_provider", return_value=mock_provider):
        result = asyncio.run(svc.initiate({"first_name": "Alice", "last_name": "Smith"}, "quest json"))
    assert result["conversation_id"] == "cid-async"


@pytest.mark.unit
def test_feedback_initiate_conversation_id_from_session_id_attr():
    """initiate() falls back to session._session_id attribute when _get_session_id is absent."""
    svc = _feedback_svc()
    svc.session = MagicMock(spec=[])
    svc.session._session_id = "cid-attr"
    tf_resp = MagicMock()
    tf_resp.response = "feedback"
    tf_resp.suggested_change = None
    mock_provider = MagicMock()
    mock_provider.run_conversation = AsyncMock(return_value=MagicMock(final_output=tf_resp))
    with patch("services.conversation.teacher_feedback_service.get_bot_provider", return_value=mock_provider):
        result = asyncio.run(svc.initiate({"first_name": "Alice", "last_name": "Smith"}, "quest json"))
    assert result["conversation_id"] == "cid-attr"


@pytest.mark.unit
def test_feedback_initiate_conversation_id_none_when_no_session_id():
    """initiate() returns conversation_id=None when the session exposes no usable ID."""
    svc = _feedback_svc()
    svc.session = MagicMock(spec=[])
    tf_resp = MagicMock()
    tf_resp.response = "feedback"
    tf_resp.suggested_change = None
    mock_provider = MagicMock()
    mock_provider.run_conversation = AsyncMock(return_value=MagicMock(final_output=tf_resp))
    with patch("services.conversation.teacher_feedback_service.get_bot_provider", return_value=mock_provider):
        result = asyncio.run(svc.initiate({"first_name": "Alice", "last_name": "Smith"}, "quest json"))
    assert result["conversation_id"] is None


@pytest.mark.unit
def test_feedback_initiate_happy_path():
    svc = _feedback_svc()
    tf_resp = MagicMock()
    tf_resp.response = "Here is my feedback"
    tf_resp.suggested_change = None
    mock_provider = MagicMock()
    mock_provider.run_conversation = AsyncMock(return_value=MagicMock(final_output=tf_resp))
    svc._extract_conversation_id = AsyncMock(return_value="cid-1")
    with patch("services.conversation.teacher_feedback_service.get_bot_provider", return_value=mock_provider):
        result = asyncio.run(svc.initiate({"first_name": "Alice", "last_name": "Smith"}, "quest json"))
    assert result["response"] == "Here is my feedback"
    assert result["conversation_id"] == "cid-1"
    assert "suggested_change" in result
    call_args = mock_provider.run_conversation.call_args
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
    mock_provider = MagicMock()
    mock_provider.run_conversation = AsyncMock(return_value=MagicMock(final_output=tf_resp))
    svc._extract_conversation_id = AsyncMock(return_value=None)
    with patch("services.conversation.teacher_feedback_service.get_bot_provider", return_value=mock_provider):
        asyncio.run(svc.initiate({}, "summary"))
    call_message = mock_provider.run_conversation.call_args[0][1]
    assert "summary" in call_message


@pytest.mark.unit
def test_feedback_continue_happy_path():
    svc = _feedback_svc()
    tf_resp = MagicMock()
    tf_resp.response = "Updated"
    tf_resp.suggested_change = {"week": 3}
    mock_provider = MagicMock()
    mock_provider.run_conversation = AsyncMock(return_value=MagicMock(final_output=tf_resp))
    with patch("services.conversation.teacher_feedback_service.get_bot_provider", return_value=mock_provider):
        result = asyncio.run(svc.continue_conversation("Adjust week 3"))
    assert result["response"] == "Updated"
    assert result["suggested_change"] == {"week": 3}
    call_args = mock_provider.run_conversation.call_args
    assert call_args[0][0] is svc.agent
    assert call_args[0][1] == "Adjust week 3"
    assert call_args[1]["session"] is svc.session


@pytest.mark.unit
def test_feedback_continue_returns_no_conversation_id():
    svc = _feedback_svc()
    tf_resp = MagicMock()
    tf_resp.response = "Done"
    tf_resp.suggested_change = None
    mock_provider = MagicMock()
    mock_provider.run_conversation = AsyncMock(return_value=MagicMock(final_output=tf_resp))
    with patch("services.conversation.teacher_feedback_service.get_bot_provider", return_value=mock_provider):
        result = asyncio.run(svc.continue_conversation("Hi"))
    assert "conversation_id" not in result


@pytest.mark.unit
def test_initiate_teacher_feedback_sync_wrapper():
    with patch("services.conversation.teacher_feedback_service.TeacherFeedbackConversationService") as MockCls:
        with patch("services.conversation.teacher_feedback_service.asyncio.run", return_value={"response": "X"}) as mock_run:
            MockCls.return_value.initiate = MagicMock(return_value={"response": "X"})
            initiate_teacher_feedback({"first_name": "Bob"}, "summary", conversation_id="cid-old")
    MockCls.assert_called_once_with("cid-old")
    mock_run.assert_called_once()


@pytest.mark.unit
def test_continue_teacher_feedback_sync_wrapper():
    with patch("services.conversation.teacher_feedback_service.TeacherFeedbackConversationService") as MockCls:
        with patch("services.conversation.teacher_feedback_service.asyncio.run", return_value={"response": "Y"}) as mock_run:
            MockCls.return_value.continue_conversation = MagicMock(return_value={"response": "Y"})
            continue_teacher_feedback("cid-1", "Follow up message")
    MockCls.assert_called_once_with("cid-1")
    mock_run.assert_called_once()
