"""
Reference patterns for using the backend tracking module.

Read-only — not imported at runtime.
"""

from __future__ import annotations

import time

from services.tracking import (
    Events,
    group_identify_period,
    identify_user,
    track_event,
)


# ----- 1. Quest-graded — fired from services/quest/quest_grading_service.py
def example_quest_graded(quest, grade, skills, t0: float, model: str) -> None:
    mastered = sum(1 for s in skills if s.mastered)
    track_event(
        user_id=quest.user_id,
        event=Events.QUEST_GRADED,
        properties={
            "quest_id": quest.quest_id,
            "period_id": quest.period_id,
            "week": quest.week,
            "graded_by": "ai",
            "overall_score_band": _score_to_band(grade.overall_score),
            "skill_mastery_count": mastered,
            "skill_total_count": len(skills),
            "duration_ms": int((time.time() - t0) * 1000),
            "ai_model": model,
        },
    )


def _score_to_band(score: float) -> str:
    if score < 60:
        return "below_60"
    if score < 70:
        return "60_to_69"
    if score < 80:
        return "70_to_79"
    if score < 90:
        return "80_to_89"
    return "90_to_100"


# ----- 2. Server-side enrollment — fired from services/enrollment/enrollment_service.py
def example_student_period_joined(user_id: str, period_id: str, source: str) -> None:
    track_event(
        user_id=user_id,
        event=Events.STUDENT_PERIOD_JOINED,
        properties={"period_id": period_id, "source": source},
    )


# ----- 3. Snapshot sync — daily cron, scripts/snapshot_telemetry.py
def example_snapshot_period(period: dict, counts: dict) -> None:
    group_identify_period(
        period_id=period["period_id"],
        traits={
            "name": period["course_name"],
            "owner_role": period["owner_role"],
            "owner_user_id": period["owner_user_id"],
            "has_canvas_link": bool(period.get("canvas_course_id")),
            "enrolled_student_count": counts["enrolled"],
            "active_student_count_30d": counts["active_30d"],
            "quest_count": counts["quests"],
            "graded_quest_count": counts["graded"],
            "avg_skill_mastery_pct": counts["mastery_pct"],
        },
    )


# ----- 4. Identify-from-snapshot
def example_snapshot_user(user: dict) -> None:
    identify_user(
        user_id=user["user_id"],
        traits={
            "role": user["role"],
            "email": user["email"],
            "school_name": user.get("school_name"),
            "last_login_at": user.get("last_login"),
            "has_completed_tutorial": user.get("completed_tutorial", False),
            "is_internal": False,
        },
    )
