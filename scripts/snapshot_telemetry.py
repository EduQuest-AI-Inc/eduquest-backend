"""
Daily PostHog snapshot sync.

Runs from cron / Supabase scheduled function. Pulls counts from Postgres
and pushes them as PostHog person + group traits via the centralized
tracking module.

Usage:
    python -m scripts.snapshot_telemetry

Env required:
    POSTHOG_API_KEY    # PostHog project key (server-side)
    POSTHOG_HOST       # default https://us.i.posthog.com
    SUPABASE_URL
    SUPABASE_SERVICE_ROLE_KEY
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timedelta, timezone

from services.tracking import (
    group_identify_period,
    identify_user,
    shutdown_posthog,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("snapshot_telemetry")


# ---------------------------------------------------------------------------
# Supabase access
# ---------------------------------------------------------------------------

def _supabase():
    from supabase import create_client  # local import — keeps top-level fast

    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)


# ---------------------------------------------------------------------------
# User snapshot
# ---------------------------------------------------------------------------

def sync_users(sb) -> int:
    """Push current trait values for every active user."""
    rows = (
        sb.table("user")
        .select(
            "user_id, email, role, school_name, last_login, "
            "student(completed_tutorial, strength, directory_info_opt_out, age_band, grade), "
            "teacher(pilot_approved), "
            "parent(linked_student_ids, vpc_verified_at)"
        )
        .is_("deleted_at", "null")
        .execute()
    )
    count = 0
    for r in rows.data or []:
        traits = {
            "role": r["role"],
            "email": r["email"],
            "school_name": r.get("school_name"),
            "last_login_at": r.get("last_login"),
            "is_internal": False,
        }
        if r.get("student"):
            s = r["student"][0] if isinstance(r["student"], list) else r["student"]
            traits.update(
                has_completed_tutorial=s.get("completed_tutorial", False),
                has_completed_profile_assistant=bool(s.get("strength") or []),
                directory_info_opt_out=bool(s.get("directory_info_opt_out", False)),
                age_band=s.get("age_band"),
                grade=s.get("grade"),
            )
        if r.get("teacher"):
            t = r["teacher"][0] if isinstance(r["teacher"], list) else r["teacher"]
            traits.update(pilot_approved=bool(t.get("pilot_approved", False)))
        if r.get("parent"):
            p = r["parent"][0] if isinstance(r["parent"], list) else r["parent"]
            traits.update(
                linked_student_count=len(p.get("linked_student_ids") or []),
                vpc_verified_at=p.get("vpc_verified_at"),
            )

        identify_user(user_id=r["user_id"], traits=traits)
        count += 1
    log.info("synced %d users", count)
    return count


# ---------------------------------------------------------------------------
# Period (group) snapshot
# ---------------------------------------------------------------------------

def sync_periods(sb) -> int:
    """Push counts and configuration traits for every period."""
    periods = sb.table("period").select("*").execute().data or []
    cutoff_30d = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()

    count = 0
    for p in periods:
        period_id = p["period_id"]

        enrolled = (
            sb.table("enrollment").select("user_id", count="exact").eq("period_id", period_id).execute()
        )
        quests = (
            sb.table("quest").select("quest_id, grade, last_updated_at", count="exact").eq("period_id", period_id).execute()
        )
        quest_rows = quests.data or []
        graded = sum(1 for q in quest_rows if q.get("grade"))
        active_30d_users = {q["user_id"] for q in quest_rows if q.get("last_updated_at", "") > cutoff_30d for q in [q]}

        # avg skill mastery — read aggregated-metrics if present, else null
        mastery_pct = _avg_mastery_for_period(sb, period_id)

        group_identify_period(
            period_id=period_id,
            traits={
                "name": p.get("name") or p.get("course"),
                "course_name": p.get("name") or p.get("course"),
                "owner_role": _owner_role(sb, p["owner_id"]),
                "owner_user_id": p["owner_id"],
                "school_name": p.get("school_name"),
                "has_canvas_link": bool(p.get("canvas_course_id")),
                "canvas_course_id": p.get("canvas_course_id"),
                "enrolled_student_count": enrolled.count or 0,
                "active_student_count_30d": len(active_30d_users),
                "quest_count": len(quest_rows),
                "graded_quest_count": graded,
                "avg_skill_mastery_pct": mastery_pct,
                "created_at": p.get("created_at"),
            },
        )
        count += 1
    log.info("synced %d periods", count)
    return count


def _owner_role(sb, owner_user_id: str) -> str:
    user = sb.table("user").select("role").eq("user_id", owner_user_id).single().execute()
    role = (user.data or {}).get("role")
    return "parent" if role == "parent" else "teacher"


def _avg_mastery_for_period(sb, period_id: str):
    try:
        res = (
            sb.table("aggregated_metrics")
            .select("percentage")
            .eq("period_id", period_id)
            .execute()
        )
        rows = res.data or []
        if not rows:
            return None
        return round(sum(r["percentage"] for r in rows) / len(rows), 2)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    sb = _supabase()
    sync_users(sb)
    sync_periods(sb)
    shutdown_posthog()
    return 0


if __name__ == "__main__":
    sys.exit(main())
