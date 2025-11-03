import os
import sys
import uuid
from datetime import datetime, timezone, timedelta

import pytest

# Make backend importable
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data_access.enrollment_dao import EnrollmentDAO
from models.enrollment import Enrollment

@pytest.mark.integration
def test_get_enrollments_by_student_id_gsi():
    # Ensure your backend points to the test tables (if you use env-based switching)
    os.environ['USE_TEST_TABLES'] = 'true'

    dao = EnrollmentDAO()

    # Use a unique student_id to avoid collisions with existing data
    student_id = f"stu_{uuid.uuid4().hex[:8]}"
    period_a = f"PERIOD_A_{uuid.uuid4().hex[:4]}"
    period_b = f"PERIOD_B_{uuid.uuid4().hex[:4]}"

    # Explicit, deterministic timestamps so we can assert on presence
    t0 = datetime.now(timezone.utc)
    t1 = (t0 - timedelta(minutes=2)).isoformat()
    t2 = (t0 - timedelta(minutes=1)).isoformat()
    t3 = t0.isoformat()

    e1 = Enrollment(student_id=student_id, period_id=period_a, semester="Fall 2025", enrolled_at=t1)
    e2 = Enrollment(student_id=student_id, period_id=period_b, semester="Fall 2025", enrolled_at=t2)
    e3 = Enrollment(student_id=student_id, period_id=period_a, semester="Fall 2025", enrolled_at=t3)

    # Create items
    dao.add_enrollment(e1)
    dao.add_enrollment(e2)
    dao.add_enrollment(e3)

    try:
        # Act: query by student_id via GSI
        items = dao.get_enrollments_by_student_id(student_id)

        # Assert: got exactly the 3 we inserted for this student
        assert isinstance(items, list)
        assert len(items) >= 3  # allow other data; we’ll assert the presence of ours below

        # Build a set of (period_id, enrolled_at) tuples for simple matching
        got = {(it["period_id"], it["enrolled_at"]) for it in items if it.get("student_id") == student_id}

        expected = {
            (period_a, t1),
            (period_b, t2),
            (period_a, t3),
        }

        # All expected enrollments are present
        assert expected.issubset(got)

        # Optional: if your GSI SK is enrolled_at and you want reverse-chronological order,
        # you can set ScanIndexForward=False in the DAO and then assert ordering here.
        # For now we only assert presence, since ordering isn’t enforced in the DAO.
    finally:
        # Cleanup (best-effort)
        dao.delete_enrollment(period_a, t1)
        dao.delete_enrollment(period_b, t2)
        dao.delete_enrollment(period_a, t3)