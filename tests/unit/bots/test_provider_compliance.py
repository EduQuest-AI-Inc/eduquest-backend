from bots.protocol import BotProviderProtocol
from bots.provider import MockBotProvider


def test_mock_provider_satisfies_protocol():
    assert isinstance(MockBotProvider(), BotProviderProtocol)
