"""
Bot provider — factory for real and mock bot instances.

Usage:
    from bots.provider import get_bot_provider

    agent = get_bot_provider().create_hw_agent(student, period, schedule)

Set MOCK_AI=true in your environment to use fast mock implementations
that return instant hardcoded responses without hitting the OpenAI API.

For programmatic override (e.g. pytest):
    from bots.provider import set_bot_provider, MockBotProvider
    set_bot_provider(MockBotProvider())
    ...
    set_bot_provider(None)  # reset to env-var-driven default
"""
import os
from typing import Optional

_provider_instance = None


class BotProvider:
    """Returns real bot instances. All imports are lazy to avoid loading the
    OpenAI SDK at module import time when it isn't needed."""

    def create_hw_agent(self, student, period, schedule, conversation_id=None, previous_response_id=None):
        from bots.agent import HWAgent
        return HWAgent(
            student, period, schedule,
            conversation_id=conversation_id,
            previous_response_id=previous_response_id,
        )

    def create_grading_orchestrator(self):
        from bots.grading_agent import GradingOrchestrator
        return GradingOrchestrator()

    def create_schedule_agent(self, vector_store_id: Optional[str], course_name: Optional[str] = None):
        from bots.schedule_agent import PeriodScheduleAgent
        return PeriodScheduleAgent(vector_store_id=vector_store_id, course_name=course_name)

    @property
    def runner(self):
        from agents import Runner
        return Runner


class MockBotProvider(BotProvider):
    """Returns fast mock implementations. Real Agent objects are still created
    for conversation bots (they're cheap — no network calls) so MockRunner can
    read agent.output_type to dispatch the right response type."""

    def create_hw_agent(self, student, period, schedule, conversation_id=None, previous_response_id=None):
        from bots.mocks import MockHWAgent
        return MockHWAgent(
            student, period, schedule,
            conversation_id=conversation_id,
            previous_response_id=previous_response_id,
        )

    def create_grading_orchestrator(self):
        from bots.mocks import MockGradingOrchestrator
        return MockGradingOrchestrator()

    def create_schedule_agent(self, vector_store_id: Optional[str], course_name: Optional[str] = None):
        from bots.mocks import MockPeriodScheduleAgent
        return MockPeriodScheduleAgent(vector_store_id=vector_store_id, course_name=course_name)

    @property
    def runner(self):
        from bots.mocks import MockRunner
        return MockRunner


def get_bot_provider() -> BotProvider:
    global _provider_instance
    if _provider_instance is None:
        if os.getenv("MOCK_AI", "").lower() in ("true", "1", "yes"):
            _provider_instance = MockBotProvider()
        else:
            _provider_instance = BotProvider()
    return _provider_instance


def set_bot_provider(provider: Optional[BotProvider]) -> None:
    """Override the global provider. Pass None to reset to env-var-driven default."""
    global _provider_instance
    _provider_instance = provider
