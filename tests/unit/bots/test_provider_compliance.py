import pytest

from bots.protocol import BotProviderProtocol, PptxAgentProtocol
from bots.provider import MockBotProvider
from bots._mocks import MockPptxAgent


@pytest.mark.unit
def test_mock_provider_satisfies_protocol():
    assert isinstance(MockBotProvider(), BotProviderProtocol)


@pytest.mark.unit
def test_mock_pptx_agent_satisfies_protocol():
    assert isinstance(MockPptxAgent(), PptxAgentProtocol)
