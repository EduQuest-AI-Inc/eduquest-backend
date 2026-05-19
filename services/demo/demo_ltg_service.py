"""
Demo LTG service — generates a long-term goal and 4 quests for the landing page demo.

No auth, no persistence. Single Runner.run call via DemoLTGAgent.
"""
import logging
from agents import Runner

from bots.protocol import BotProviderProtocol

logger = logging.getLogger(__name__)


class DemoLTGService:
    def __init__(self, *, bot_provider: BotProviderProtocol) -> None:
        self._bot_provider = bot_provider

    async def generate(self, grade: str, interests: list[str], subject: str) -> dict:
        logger.info("Demo LTG generation started — grade=%s subject=%s interests=%s", grade, subject, interests)
        agent = self._bot_provider.create_demo_ltg_agent(grade, interests, subject)
        result = await Runner.run(agent, input="Generate the learning plan.")
        output = result.final_output
        logger.info("Demo LTG generation complete")
        return output.model_dump()
