import pytest

# Integration fixture conventions:
#   1. Always delete-before-insert for any fixture using a fixed ID — leftover rows
#      from crashed runs cause duplicate-key ERRORs across all dependent tests.
#   2. Print at the start of setup so fixture failures are locatable in pytest output.

_STUDENT_ID = "test-integration-student-svc"
_PARENT_ID = "test-integration-parent-svc"


@pytest.fixture
def db_student(supabase_required):
    """Student row (user + student tables) for service-level tests."""
    from data_access.student_dao import StudentDAO
    from models.student import Student

    dao = StudentDAO()
    student = Student(
        user_id=_STUDENT_ID,
        first_name="Svc",
        last_name="Student",
        email="test-integration-student-svc@eduquestai.org",
        password="hashed",
        role="student",
        grade=10,
    )
    print(f"\n[fixture] db_student setup: pre-deleting {student.user_id}")
    dao.delete_student(student.user_id)
    dao.add_student(student)
    yield student
    dao.delete_student(student.user_id)


@pytest.fixture
def db_parent(supabase_required):
    """Parent row (user + parent tables) for service-level tests."""
    from data_access.parent_dao import ParentDAO
    from models.parent import Parent

    dao = ParentDAO()
    parent = Parent(
        user_id=_PARENT_ID,
        first_name="Svc",
        last_name="Parent",
        email="test-integration-parent-svc@eduquestai.org",
        password="hashed",
        role="parent",
    )
    print(f"\n[fixture] db_parent setup: pre-deleting {parent.user_id}")
    dao.delete_parent(parent.user_id)
    dao.add_parent(parent)
    yield parent
    dao.delete_parent(parent.user_id)


@pytest.fixture
def db_enrollment(supabase_required, db_student, db_period):
    """Enrollment linking db_student to db_period."""
    from data_access.enrollment_dao import EnrollmentDAO
    from models.enrollment import Enrollment

    dao = EnrollmentDAO()
    enrollment = Enrollment(
        user_id=db_student.user_id,
        period_id=db_period.period_id,
    )
    print(f"\n[fixture] db_enrollment setup: {db_student.user_id} → {db_period.period_id}")
    dao.delete_enrollment(db_student.user_id, db_period.period_id)
    dao.add_enrollment(enrollment)
    yield enrollment
    dao.delete_enrollment(db_student.user_id, db_period.period_id)
