import sys
import os
from datetime import datetime, timezone

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data_access.conversation_dao import ConversationDAO
from models.conversation import Conversation

def test_crud_operations() -> None:
    dao = ConversationDAO()

    now = datetime.now(timezone.utc).isoformat()
    conversation = Conversation(
        conversation_id="conv_test",
        user_id="student_test",
        role="student",
        conversation_type="initial",
        period_id="period_test"
    )

    # -------Add-------
    # dao.add_conversation(conversation)

    # -------Update-------
    # dao.update_conversation(
    #     conversation_id=conversation.conversation_id,
    #     updates={"conversation_type": "updated"}
    # )

    # -------Get-------
    result = dao.get_conversations_by_id("conv_test")
    print(result)

    # -------Delete-------
    # dao.delete_conversation(conversation.conversation_id)
    # final = dao.get_conversations_by_id("conv_test")
    # assert not any(c["user_id"] == "student_test" for c in final)

test_crud_operations()
