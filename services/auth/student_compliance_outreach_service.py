from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone

from data_access.parent_dao import ParentDAO
from data_access.student_dao import StudentDAO
from data_access.user_dao import UserDAO
from integrations.email_service import get_email_service

logger = logging.getLogger(__name__)


@dataclass
class OutreachResult:
    candidates: int
    sent: int
    skipped: int
    failed: int


class StudentComplianceOutreachService:
    def __init__(self, student_dao=None, parent_dao=None, user_dao=None, email_service=None) -> None:
        self.student_dao = student_dao or StudentDAO()
        self.parent_dao = parent_dao or ParentDAO()
        self.user_dao = user_dao or UserDAO()
        self.email_service = email_service or get_email_service()

    def run_pass(self, now: datetime | None = None) -> OutreachResult:
        if os.getenv("STUDENT_COMPLIANCE_OUTREACH_ENABLED", "").lower() not in ("1", "true", "yes"):
            raise RuntimeError("STUDENT_COMPLIANCE_OUTREACH_ENABLED must be true")
        if os.getenv("STUDENT_COMPLIANCE_OUTREACH_COPY_APPROVED", "").lower() not in ("1", "true", "yes"):
            raise RuntimeError("Counsel-approved outreach copy is required before sending")

        now = now or datetime.now(timezone.utc)
        records = self.student_dao.list_legacy_review_due()
        sent = skipped = failed = 0

        for student in records:
            due_raw = student.get("compliance_review_due_at")
            if not due_raw:
                skipped += 1
                continue
            due = datetime.fromisoformat(due_raw.replace("Z", "+00:00"))
            stage = self._stage_for_days_remaining((due - now).days)
            if stage <= int(student.get("compliance_outreach_stage") or 0):
                skipped += 1
                continue

            recipients = self._recipients(student)
            if not recipients:
                skipped += 1
                continue
            results = [
                self.email_service.send_student_compliance_outreach_email(
                    to_email=email,
                    deadline=due.date().isoformat(),
                )
                for email in recipients
            ]
            successes = [r for r in results if r.get("success")]
            failures = [r for r in results if not r.get("success")]
            if failures:
                logger.warning(
                    "student_compliance_outreach: %d/%d emails failed for student %s",
                    len(failures), len(results), student["user_id"],
                )
                failed += len(failures)
            if successes:
                sent += len(successes)
            # Always bump stage to prevent duplicate sends to recipients who succeeded
            self.student_dao.update_student(
                student["user_id"],
                {
                    "compliance_outreach_stage": stage,
                    "compliance_outreach_sent_at": now.isoformat(),
                },
            )

        logger.info(
            "student_compliance_outreach.pass candidates=%d sent=%d skipped=%d failed=%d",
            len(records), sent, skipped, failed,
        )
        return OutreachResult(candidates=len(records), sent=sent, skipped=skipped, failed=failed)

    def _recipients(self, student: dict) -> set[str]:
        recipients = {student["email"].strip().lower()} if student.get("email") else set()
        for parent in self.parent_dao.get_parents_by_student_id(student["user_id"]):
            parent_user = self.user_dao.get_by_id(parent["user_id"])
            if parent_user and parent_user.get("email"):
                recipients.add(parent_user["email"].strip().lower())
        return recipients

    @staticmethod
    def _stage_for_days_remaining(days_remaining: int) -> int:
        if days_remaining <= 1:
            return 4
        if days_remaining <= 7:
            return 3
        if days_remaining <= 14:
            return 2
        return 1
