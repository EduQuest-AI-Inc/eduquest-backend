"""
Source of truth for backend PostHog event names.

Mirror of `eduquest-frontend/lib/tracking/events.ts`. Keep these in sync.
Generated from `.telemetry/tracking-plan.yaml` v1.

Rule: NEVER pass a raw string event name to track_event().
Always reference `Events.X`.
"""

from __future__ import annotations


class Events:
    # ------- Lifecycle (server-fired) -------
    USER_SIGNUP_FAILED = "user_signup_failed"
    USER_LOGIN_FAILED = "user_login_failed"
    PASSWORD_RESET_REQUESTED = "password_reset_requested"
    PASSWORD_RESET_COMPLETED = "password_reset_completed"

    # ------- Core value (server) -------
    QUESTS_GENERATED = "quests_generated"
    SCHEDULE_GENERATED = "schedule_generated"
    QUEST_GRADED = "quest_graded"
    SKILL_MASTERY_UPDATED = "skill_mastery_updated"

    # ------- Collaboration (server) -------
    STUDENT_PERIOD_JOINED = "student_period_joined"
    PARENT_INVITE_SENT = "parent_invite_sent"
    PARENT_INVITE_ACCEPTED = "parent_invite_accepted"

    # ------- Configuration (server) -------
    PERIOD_FILES_UPLOADED = "period_files_uploaded"

    # ------- Billing errors (server) -------
    BILLING_CHECKOUT_FAILED          = "billing_checkout_failed"
    BILLING_PORTAL_FAILED            = "billing_portal_failed"
    MEMBERSHIP_TRIAL_CREATION_FAILED = "membership_trial_creation_failed"

    # ------- AI pipeline failures (server) -------
    QUEST_GRADING_FAILED    = "quest_grading_failed"
    QUEST_GENERATION_FAILED = "quest_generation_failed"
    SUMMER_QUEST_GEN_FAILED = "summer_quest_generation_failed"
    PERIOD_FILE_PROC_FAILED = "period_file_processing_failed"
    PPTX_LESSON_GEN_FAILED  = "pptx_lesson_generation_failed"
    CURRICULUM_GEN_FAILED   = "curriculum_generation_failed"
    GRADE_PERSISTENCE_FAILED = "grade_persistence_failed"
    QUEST_UPDATE_FAILED     = "quest_update_failed"

    # ------- Integration errors (server) -------
    CANVAS_CONNECT_FAILED = "canvas_connect_failed"

    # ------- Access gating (server) -------
    PILOT_WAITLIST_APPROVED = "pilot_waitlist_approved"
