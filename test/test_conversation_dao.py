import sys
import os
from datetime import datetime, timezone

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data_access.conversation_dao import ConversationDAO
from models.conversation import Conversation

def test_crud_operations():
    dao = ConversationDAO()

    now = datetime.now(timezone.utc).isoformat()
    conversation = Conversation(
        thread_id="thread_test",
        student_id="student_test",
        conversation_type="initial",
        last_updated_at=now,
        created_at=now
    )

    # -------Add-------
    dao.add_conversation(conversation)

    # -------Update-------
    # dao.update_conversation(
    #     thread_id=conversation.thread_id,
    #     last_updated_at="2025-05-17T19:05:43.525528+00:00",
    #     updates={"conversation_type": "updated"}
    # )

    # -------Get-------
    result = dao.get_conversations_by_thread("thread_test")
    print(result)

    # -------Delete-------
    # dao.delete_conversation(conversation.thread_id, "2025-05-17T19:10:40.189374+00:00")
    # final = dao.get_conversations_by_thread("thread_test")
    # assert not any(c["student_id"] == "student_test" for c in final)

test_crud_operations()
