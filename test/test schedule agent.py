"""
DEPRECATED: This test file is no longer applicable.

SchedulesAgent has been removed from the codebase. Quest generation now uses:
1. Teacher-defined period_schedule with quest_enabled_weeks
2. HWAgent to generate homework for those enabled weeks

See the new quest-weeks flow in routes/period/period_service.py:start_homework_agent
"""

# This test file has been deprecated. The SchedulesAgent class no longer exists.
# Quest scheduling is now handled via the centralized period_schedule table.

raise NotImplementedError(
    "SchedulesAgent has been removed. "
    "Quest generation now uses period_schedule.quest_enabled_weeks + HWAgent."
)
