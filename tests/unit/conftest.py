import sys
import pytest


# Keys that must stay mocked for unit tests. The bots conftest removes these
# during its module fixture; this restores them between test modules so no
# unit test ever sees un-mocked bots/agents regardless of execution order.
_UNIT_MOCK_KEYS = [
    "bots",
    "bots.quest_agent",
    "bots.profile_agent",
    "bots.ltg_agent",
    "bots.grading_agent",
    "bots.teacher_feedback_agent",
    "bots.coverage_evaluator",
    "bots.guardrails",
    "bots.schemas",
    "bots.schemas.rubric",
    "bots.provider",
    "bots.slideshow",
    "bots.slideshow.pptx_agent",
    "bots.slideshow.orchestrator_agent",
    "bots.slideshow.content_writer_agent",
    "bots.slideshow.visual_review_agent",
    "bots.tools",
    "bots.tools.content_tool",
    "bots.tools.image_tool",
    "bots.tools.chart_tool",
    "bots.tools.review_tool",
    "bots.tools.html_tool",
    "agents",
    "agents._config",
    "agents.models",
    "agents.model_settings",
]


@pytest.fixture(autouse=True)
def ensure_unit_mocks(request):
    """Re-apply bots/agents sys.modules mocks before each unit test.

    The bots test module temporarily removes these mocks (to import real bots
    code) and restores them after. This fixture guarantees they are present for
    every non-bots unit test even if test ordering shifts in the future.
    """
    if "unit/bots" in str(request.fspath):
        yield
        return

    from unittest.mock import MagicMock
    missing = [k for k in _UNIT_MOCK_KEYS if k not in sys.modules]
    for key in missing:
        sys.modules[key] = MagicMock()
    yield
