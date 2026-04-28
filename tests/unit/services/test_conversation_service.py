import json
import pytest
from unittest.mock import MagicMock, patch

from services.conversation.conversation_service import ConversationService

_STUDENT_SESSION = [{"user_id": "u1", "role": "student"}]
_TEACHER_SESSION = [{"user_id": "t1", "role": "teacher"}]
_VALID_QUESTS_FILE = json.dumps([{"period_id": "p1", "week": 1}])


def _svc():
    svc = ConversationService.__new__(ConversationService)
    svc.session_dao = MagicMock()
    svc.student_dao = MagicMock()
    svc.conversation_dao = MagicMock()
    svc.teacher_dao = MagicMock()
    svc.period_dao = MagicMock()
    return svc


# ---------------------------------------------------------------------------
# start_profile_assistant
# ---------------------------------------------------------------------------

@pytest.mark.unit
@patch("services.conversation.conversation_service.initiate_profile_conversation",
       return_value={"response_id": "rid1", "response": "Hello!"})
def test_start_profile_assistant_happy_path(mock_init):
    svc = _svc()
    svc.session_dao.get_sessions_by_auth_token.return_value = _STUDENT_SESSION
    svc.student_dao.get_student_by_id.return_value = {"user_id": "u1"}

    result = svc.start_profile_assistant("token")

    assert "conversation_id" in result
    assert result["response"] == "Hello!"
    svc.conversation_dao.add_conversation.assert_called_once()


@pytest.mark.unit
def test_start_profile_assistant_invalid_auth():
    svc = _svc()
    svc.session_dao.get_sessions_by_auth_token.return_value = []

    with pytest.raises(Exception, match="Invalid auth token"):
        svc.start_profile_assistant("bad-token")


@pytest.mark.unit
@patch("services.conversation.conversation_service.initiate_profile_conversation")
def test_start_profile_assistant_student_not_found(mock_init):
    svc = _svc()
    svc.session_dao.get_sessions_by_auth_token.return_value = _STUDENT_SESSION
    svc.student_dao.get_student_by_id.return_value = None

    with pytest.raises(Exception, match="Student not found"):
        svc.start_profile_assistant("token")


@pytest.mark.unit
@patch("services.conversation.conversation_service.initiate_profile_conversation",
       return_value={"response": "Hello!"})
def test_start_profile_assistant_no_response_id(mock_init):
    svc = _svc()
    svc.session_dao.get_sessions_by_auth_token.return_value = _STUDENT_SESSION
    svc.student_dao.get_student_by_id.return_value = {"user_id": "u1"}

    with pytest.raises(Exception, match="Failed to obtain response_id"):
        svc.start_profile_assistant("token")


# ---------------------------------------------------------------------------
# continue_profile_assistant
# ---------------------------------------------------------------------------

@pytest.mark.unit
@patch("services.conversation.conversation_service.continue_profile_conversation",
       return_value={"response": "Next!", "response_id": "rid2"})
def test_continue_profile_assistant_happy_path(mock_cont):
    svc = _svc()
    svc.session_dao.get_sessions_by_auth_token.return_value = _STUDENT_SESSION
    svc.conversation_dao.get_conversation_by_id_user_type.return_value = {
        "last_response_id": "rid1"
    }

    result = svc.continue_profile_assistant("token", "profile", "cid1", "Hi")

    assert result["response"] == "Next!"
    assert result["profile_complete"] is False
    svc.conversation_dao.update_conversation.assert_called_once_with("cid1", {"last_response_id": "rid2"})


@pytest.mark.unit
@patch("services.conversation.conversation_service.continue_profile_conversation",
       return_value={
           "response": "Done!",
           "response_id": "rid2",
           "profile_complete": True,
           "profile": {"interest": "math"},
       })
def test_continue_profile_assistant_profile_complete(mock_cont):
    svc = _svc()
    svc.session_dao.get_sessions_by_auth_token.return_value = _STUDENT_SESSION
    svc.conversation_dao.get_conversation_by_id_user_type.return_value = {"last_response_id": "rid1"}

    result = svc.continue_profile_assistant("token", "profile", "cid1", "Hi")

    assert result["profile_complete"] is True
    svc.student_dao.update_student.assert_called_once_with("u1", {"interest": "math"})


@pytest.mark.unit
@patch("services.conversation.conversation_service.continue_profile_conversation",
       return_value={"response": "Hmm"})
def test_continue_profile_assistant_no_new_response_id(mock_cont):
    svc = _svc()
    svc.session_dao.get_sessions_by_auth_token.return_value = _STUDENT_SESSION
    svc.conversation_dao.get_conversation_by_id_user_type.return_value = {"last_response_id": "rid1"}

    svc.continue_profile_assistant("token", "profile", "cid1", "Hi")

    svc.conversation_dao.update_conversation.assert_not_called()


@pytest.mark.unit
def test_continue_profile_assistant_invalid_auth():
    svc = _svc()
    svc.session_dao.get_sessions_by_auth_token.return_value = []

    with pytest.raises(Exception, match="Invalid auth token"):
        svc.continue_profile_assistant("bad", "profile", "cid1", "Hi")


@pytest.mark.unit
@patch("services.conversation.conversation_service.continue_profile_conversation")
def test_continue_profile_assistant_conversation_not_found(mock_cont):
    svc = _svc()
    svc.session_dao.get_sessions_by_auth_token.return_value = _STUDENT_SESSION
    svc.conversation_dao.get_conversation_by_id_user_type.return_value = None

    with pytest.raises(Exception, match="Conversation not found"):
        svc.continue_profile_assistant("token", "profile", "cid1", "Hi")


# ---------------------------------------------------------------------------
# start_update_assistant — student path
# ---------------------------------------------------------------------------

@pytest.mark.unit
@patch("services.conversation.conversation_service.grade_student_submission",
       return_value={"grade": "A", "overall_score": 95, "feedback": "Good", "response": "Nice work!"})
def test_start_update_assistant_student_happy_path(mock_grade):
    svc = _svc()
    svc.session_dao.get_sessions_by_auth_token.return_value = _STUDENT_SESSION
    svc.student_dao.get_student_by_id.return_value = {"user_id": "u1"}
    svc.period_dao.get_period_by_id.return_value = {"period_id": "p1"}

    result = svc.start_update_assistant("token", _VALID_QUESTS_FILE, is_instructor=False)

    assert "conversation_id" in result
    assert result["response"] == "Nice work!"
    svc.conversation_dao.add_conversation.assert_called_once()


@pytest.mark.unit
@patch("services.conversation.conversation_service.upload_file_to_s3", return_value="s3/key/file")
@patch("services.conversation.conversation_service.grade_student_submission",
       return_value={"grade": "B", "overall_score": 80, "feedback": "OK", "response": "Done"})
def test_start_update_assistant_student_with_submission(mock_grade, mock_s3):
    svc = _svc()
    svc.session_dao.get_sessions_by_auth_token.return_value = _STUDENT_SESSION
    svc.student_dao.get_student_by_id.return_value = {"user_id": "u1"}
    svc.period_dao.get_period_by_id.return_value = {"period_id": "p1"}

    result = svc.start_update_assistant(
        "token", _VALID_QUESTS_FILE, is_instructor=False,
        submission_file="/tmp/file.pdf", individual_quest_id="q1",
    )

    mock_s3.assert_called_once()
    assert result.get("s3_key") == "s3/key/file"


@pytest.mark.unit
@patch("data_access.quest_dao.QuestDAO")
@patch("services.conversation.conversation_service.grade_student_submission",
       return_value={"grade": "A", "overall_score": 90, "feedback": "Great", "response": "Saved"})
def test_start_update_assistant_student_saves_grade(mock_grade, mock_quest_dao_cls):
    svc = _svc()
    svc.session_dao.get_sessions_by_auth_token.return_value = _STUDENT_SESSION
    svc.student_dao.get_student_by_id.return_value = {"user_id": "u1"}
    svc.period_dao.get_period_by_id.return_value = {"period_id": "p1"}
    mock_quest_dao_cls.return_value = MagicMock()

    result = svc.start_update_assistant(
        "token", _VALID_QUESTS_FILE, is_instructor=False,
        week=1, individual_quest_id="q1",
    )

    assert "conversation_id" in result


@pytest.mark.unit
def test_start_update_assistant_invalid_auth():
    svc = _svc()
    svc.session_dao.get_sessions_by_auth_token.return_value = []

    with pytest.raises(Exception, match="Invalid auth token"):
        svc.start_update_assistant("bad", _VALID_QUESTS_FILE, is_instructor=False)


@pytest.mark.unit
@patch("services.conversation.conversation_service.grade_student_submission",
       return_value={"response": "X"})
def test_start_update_assistant_student_not_found(mock_grade):
    svc = _svc()
    svc.session_dao.get_sessions_by_auth_token.return_value = _STUDENT_SESSION
    svc.student_dao.get_student_by_id.return_value = None

    with pytest.raises(Exception, match="Student not found"):
        svc.start_update_assistant("token", _VALID_QUESTS_FILE, is_instructor=False)


@pytest.mark.unit
@patch("services.conversation.conversation_service.grade_student_submission",
       return_value={"response": "X"})
def test_start_update_assistant_period_not_found(mock_grade):
    svc = _svc()
    svc.session_dao.get_sessions_by_auth_token.return_value = _STUDENT_SESSION
    svc.student_dao.get_student_by_id.return_value = {"user_id": "u1"}
    svc.period_dao.get_period_by_id.return_value = None

    with pytest.raises(Exception, match="Period with id p1 not found"):
        svc.start_update_assistant("token", _VALID_QUESTS_FILE, is_instructor=False)


@pytest.mark.unit
def test_start_update_assistant_missing_quests_file():
    svc = _svc()
    svc.session_dao.get_sessions_by_auth_token.return_value = _STUDENT_SESSION
    svc.student_dao.get_student_by_id.return_value = {"user_id": "u1"}

    with pytest.raises(Exception, match="quests_file is required for students"):
        svc.start_update_assistant("token", None, is_instructor=False)


@pytest.mark.unit
def test_start_update_assistant_invalid_json():
    svc = _svc()
    svc.session_dao.get_sessions_by_auth_token.return_value = _STUDENT_SESSION
    svc.student_dao.get_student_by_id.return_value = {"user_id": "u1"}

    with pytest.raises(Exception, match="Failed to parse quests JSON"):
        svc.start_update_assistant("token", "not-json", is_instructor=False)


@pytest.mark.unit
def test_start_update_assistant_quests_not_a_list():
    svc = _svc()
    svc.session_dao.get_sessions_by_auth_token.return_value = _STUDENT_SESSION
    svc.student_dao.get_student_by_id.return_value = {"user_id": "u1"}

    with pytest.raises(Exception, match="Invalid quests data format"):
        svc.start_update_assistant("token", '{"key": "val"}', is_instructor=False)


@pytest.mark.unit
def test_start_update_assistant_no_period_id_in_quest():
    svc = _svc()
    svc.session_dao.get_sessions_by_auth_token.return_value = _STUDENT_SESSION
    svc.student_dao.get_student_by_id.return_value = {"user_id": "u1"}

    with pytest.raises(Exception, match="No period_id found in quest data"):
        svc.start_update_assistant("token", '[{}]', is_instructor=False)


# ---------------------------------------------------------------------------
# start_update_assistant — teacher/instructor path
# ---------------------------------------------------------------------------

@pytest.mark.unit
@patch("services.quest.quest_service.QuestService")
@patch("services.conversation.conversation_service.initiate_teacher_feedback",
       return_value={"conversation_id": "cid1", "response": "Feedback!"})
def test_start_update_assistant_teacher_happy_path(mock_feedback, mock_qs_cls):
    svc = _svc()
    svc.session_dao.get_sessions_by_auth_token.return_value = _TEACHER_SESSION
    svc.teacher_dao.get_teacher_by_id.return_value = {"user_id": "t1"}
    svc.student_dao.get_student_by_id.return_value = {"user_id": "t1"}
    svc.period_dao.get_period_by_id.return_value = {"period_id": "p1"}
    mock_qs_cls.return_value.get_quests_for_student.return_value = []

    result = svc.start_update_assistant(
        "token", None, is_instructor=True, period_id="p1"
    )

    assert result["conversation_id"] == "cid1"
    assert result["response"] == "Feedback!"
    svc.conversation_dao.add_conversation.assert_called_once()


@pytest.mark.unit
@patch("services.quest.quest_service.QuestService")
@patch("services.conversation.conversation_service.initiate_teacher_feedback",
       return_value={"conversation_id": "cid1", "response": "X"})
def test_start_update_assistant_teacher_not_found(mock_feedback, mock_qs_cls):
    svc = _svc()
    svc.session_dao.get_sessions_by_auth_token.return_value = _TEACHER_SESSION
    svc.teacher_dao.get_teacher_by_id.return_value = None

    with pytest.raises(Exception, match="Teacher not found"):
        svc.start_update_assistant("token", None, is_instructor=True, period_id="p1")


@pytest.mark.unit
@patch("services.quest.quest_service.QuestService")
@patch("services.conversation.conversation_service.initiate_teacher_feedback",
       return_value={"conversation_id": "cid1", "response": "X"})
def test_start_update_assistant_target_student_not_found(mock_feedback, mock_qs_cls):
    svc = _svc()
    svc.session_dao.get_sessions_by_auth_token.return_value = _TEACHER_SESSION
    svc.teacher_dao.get_teacher_by_id.return_value = {"user_id": "t1"}
    svc.period_dao.get_period_by_id.return_value = {"period_id": "p1"}
    svc.student_dao.get_student_by_id.return_value = None
    mock_qs_cls.return_value.get_quests_for_student.return_value = []

    with pytest.raises(Exception, match="Target student not found"):
        svc.start_update_assistant("token", None, is_instructor=True, period_id="p1")


@pytest.mark.unit
def test_start_update_assistant_instructor_missing_period_id():
    svc = _svc()
    svc.session_dao.get_sessions_by_auth_token.return_value = _TEACHER_SESSION
    svc.teacher_dao.get_teacher_by_id.return_value = {"user_id": "t1"}

    with pytest.raises(Exception, match="period_id is required for instructors"):
        svc.start_update_assistant("token", None, is_instructor=True, period_id=None)


# ---------------------------------------------------------------------------
# continue_update_assistant
# ---------------------------------------------------------------------------

@pytest.mark.unit
@patch("services.conversation.conversation_service.continue_teacher_feedback",
       return_value={"response": "Continuing..."})
def test_continue_update_assistant_happy_path(mock_cont):
    svc = _svc()
    svc.session_dao.get_sessions_by_auth_token.return_value = _STUDENT_SESSION
    svc.conversation_dao.get_conversation_by_id_user_type.return_value = {"period_id": "p1"}

    result = svc.continue_update_assistant("token", "cid1", "message")

    assert result["response"] == "Continuing..."


@pytest.mark.unit
@patch("services.period.period_service.PeriodService")
@patch("services.conversation.conversation_service.continue_teacher_feedback",
       return_value={"response": "Updated!", "suggested_change": {"week": 2}})
def test_continue_update_assistant_with_suggested_change(mock_cont, mock_ps_cls):
    svc = _svc()
    svc.session_dao.get_sessions_by_auth_token.return_value = _STUDENT_SESSION
    svc.conversation_dao.get_conversation_by_id_user_type.return_value = {"period_id": "p1"}
    mock_ps_cls.return_value.update_quests_with_recommended_change.return_value = {"message": "done"}

    svc.continue_update_assistant("token", "cid1", "message")

    mock_ps_cls.return_value.update_quests_with_recommended_change.assert_called_once()


@pytest.mark.unit
def test_continue_update_assistant_invalid_auth():
    svc = _svc()
    svc.session_dao.get_sessions_by_auth_token.return_value = []

    with pytest.raises(Exception, match="Invalid auth token"):
        svc.continue_update_assistant("bad", "cid1", "message")


@pytest.mark.unit
@patch("services.conversation.conversation_service.continue_teacher_feedback")
def test_continue_update_assistant_conversation_not_found(mock_cont):
    svc = _svc()
    svc.session_dao.get_sessions_by_auth_token.return_value = _STUDENT_SESSION
    svc.conversation_dao.get_conversation_by_id_user_type.return_value = None

    with pytest.raises(Exception, match="Conversation not found"):
        svc.continue_update_assistant("token", "cid1", "message")
