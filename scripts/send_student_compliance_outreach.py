"""Send gated legacy-student remediation notices and reminders."""
import logging
import sys

from dotenv import load_dotenv

load_dotenv()

from services.auth.student_compliance_outreach_service import StudentComplianceOutreachService  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)-8s %(name)s - %(message)s")


def main() -> int:
    result = StudentComplianceOutreachService().run_pass()
    print(
        f"student-compliance-outreach pass: candidates={result.candidates} "
        f"sent={result.sent} skipped={result.skipped} failed={result.failed}"
    )
    return 0 if result.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
