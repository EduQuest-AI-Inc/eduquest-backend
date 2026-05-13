"""
Cron entry-point: send trial-ending reminders.

Run with:
    python -m scripts.send_trial_reminders

Schedule daily (e.g. 09:00 UTC). Idempotent: each membership is reminded at
most once via the membership.reminder_sent_at column.
"""
from __future__ import annotations

import logging
import sys

from dotenv import load_dotenv

load_dotenv()

from services.billing.trial_reminder_service import TrialReminderService  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)-8s %(name)s - %(message)s")


def main() -> int:
    result = TrialReminderService().run_pass()
    print(
        f"trial-reminder pass: candidates={result.candidates} sent={result.sent} "
        f"skipped_no_email={result.skipped_no_email} failed={result.failed}"
    )
    return 0 if result.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
