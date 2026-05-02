"""
EduQuest backend telemetry — centralized PostHog wrapper.

Public surface:

    from services.tracking import Events, track_event, identify_user, group_identify_period
"""

from .events import Events
from .track import (
    track_event,
    identify_user,
    group_identify_period,
)
from .posthog_client import get_posthog, shutdown_posthog

__all__ = [
    "Events",
    "track_event",
    "identify_user",
    "group_identify_period",
    "get_posthog",
    "shutdown_posthog",
]
