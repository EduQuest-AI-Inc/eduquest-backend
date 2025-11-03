import sys
import os
from datetime import datetime, timezone

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from routes.auth.auth_service import register_user
from data_access.waitlist_dao import WaitlistDAO
from data_access.student_dao import StudentDAO
from data_access.teacher_dao import TeacherDAO

def test_signup_with_valid_waitlist_code():
    waitlist_dao = WaitlistDAO()
    teacher_dao = TeacherDAO()

    test_code = "VALID123"
    test_username = "testteacher1"

    waitlist_dao.table.put_item(
        Item={
            "waitlistID": test_code,
            "email": "teacher1@example.com",
            "name": "Teacher One",
            "used": False,
        }
    )

    result = register_user(
        username=test_username,
        password="password123",
        role="teacher",
        first_name="Teacher",
        last_name="One",
        email="teacher1@example.com",
        waitlist_code=test_code
    )

    assert result["success"] == True

    entry = waitlist_dao.get_by_code(test_code)
    assert entry["used"] == True
    assert entry["usedBy"] == test_username

    print("test_signup_with_valid_waitlist_code passed")

    teacher_dao.delete_teacher(test_username)
    waitlist_dao.table.delete_item(Key={"waitlistID": test_code})

def test_signup_with_invalid_waitlist_code():
    result = register_user(
        username="testteacher2",
        password="password123",
        role="teacher",
        first_name="Teacher",
        last_name="Two",
        email="teacher2@example.com",
        waitlist_code="INVALID99"
    )

    assert result["success"] == False
    assert result["error"] == "Invalid waitlist code"
    print("test_signup_with_invalid_waitlist_code passed")

def test_signup_with_used_waitlist_code():
    waitlist_dao = WaitlistDAO()

    test_code = "USED5678"

    waitlist_dao.table.put_item(
        Item={
            "waitlistID": test_code,
            "email": "teacher3@example.com",
            "name": "Teacher Three",
            "used": True,
            "usedAt": datetime.now(timezone.utc).isoformat(),
            "usedBy": "otheruser"
        }
    )

    result = register_user(
        username="testteacher3",
        password="password123",
        role="teacher",
        first_name="Teacher",
        last_name="Three",
        email="teacher3@example.com",
        waitlist_code=test_code
    )

    assert result["success"] == False
    assert result["error"] == "Waitlist code has already been used"
    print("test_signup_with_used_waitlist_code passed")

    waitlist_dao.table.delete_item(Key={"waitlistID": test_code})

def test_signup_student_with_valid_waitlist_code():
    waitlist_dao = WaitlistDAO()
    student_dao = StudentDAO()

    test_code = "STUDENT1"
    test_username = "teststudent1"

    waitlist_dao.table.put_item(
        Item={
            "waitlistID": test_code,
            "email": "student1@example.com",
            "name": "Student One",
            "used": False,
        }
    )

    result = register_user(
        username=test_username,
        password="password123",
        role="student",
        first_name="Student",
        last_name="One",
        email="student1@example.com",
        grade=10,
        waitlist_code=test_code
    )

    assert result["success"] == True

    entry = waitlist_dao.get_by_code(test_code)
    assert entry["used"] == True
    assert entry["usedBy"] == test_username

    print("test_signup_student_with_valid_waitlist_code passed")

    student_dao.delete_student(test_username)
    waitlist_dao.table.delete_item(Key={"waitlistID": test_code})

def test_signup_without_waitlist_code():
    teacher_dao = TeacherDAO()
    test_username = "testteacher4"

    result = register_user(
        username=test_username,
        password="password123",
        role="teacher",
        first_name="Teacher",
        last_name="Four",
        email="teacher4@example.com",
        waitlist_code=None
    )

    assert result["success"] == True
    print("test_signup_without_waitlist_code passed")

    teacher_dao.delete_teacher(test_username)

def run_all_tests():
    print("Running signup with waitlist integration tests...\n")

    try:
        test_signup_with_valid_waitlist_code()
        test_signup_with_invalid_waitlist_code()
        test_signup_with_used_waitlist_code()
        test_signup_student_with_valid_waitlist_code()
        test_signup_without_waitlist_code()

        print("\nAll integration tests passed!")
    except AssertionError as e:
        print(f"\nTest failed: {e}")
    except Exception as e:
        print(f"\nError running tests: {e}")

if __name__ == "__main__":
    run_all_tests()
