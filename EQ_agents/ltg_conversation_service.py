"""
Backwards-compatibility re-exports.

The agent definition now lives in ``EQ_agents/ltg_agent.py`` and the
service / session logic lives in ``routes/conversation/ltg_service.py``.
This shim keeps old imports working until they are all updated.
"""
from EQ_agents.ltg_agent import LTGResponse, create_ltg_agent  # noqa: F401
from routes.conversation.ltg_service import (  # noqa: F401
    LTGConversationService,
    initiate_ltg_conversation,
    continue_ltg_conversation,
)
