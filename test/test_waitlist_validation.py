import sys
import os
from datetime import datetime, timezone

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data_access.waitlist_dao import WaitlistDAO

def test_validate_code_success():
    dao = WaitlistDAO()

    test_code = "TEST1234"
    dao.table.put_item(
        Item={
            "waitlistID": test_code,
            "email": "test@example.com",
            "name": "Test User",
            "used": False,
        }
    )

    result = dao.validate_code(test_code)
    assert result["valid"] == True
    assert "entry" in result
    print("test_validate_code_success passed")

    dao.table.delete_item(Key={"waitlistID": test_code})

def test_validate_code_invalid():
    dao = WaitlistDAO()

    result = dao.validate_code("NONEXISTENT")
    assert result["valid"] == False
    assert result["error"] == "Invalid waitlist code"
    print("test_validate_code_invalid passed")

def test_validate_code_already_used():
    dao = WaitlistDAO()

    test_code = "USED1234"
    dao.table.put_item(
        Item={
            "waitlistID": test_code,
            "email": "used@example.com",
            "name": "Used User",
            "used": True,
            "usedAt": datetime.now(timezone.utc).isoformat(),
            "usedBy": "test_user"
        }
    )

    result = dao.validate_code(test_code)
    assert result["valid"] == False
    assert result["error"] == "Waitlist code has already been used"
    print("test_validate_code_already_used passed")

    dao.table.delete_item(Key={"waitlistID": test_code})

def test_validate_code_empty():
    dao = WaitlistDAO()

    result = dao.validate_code("")
    assert result["valid"] == False
    assert result["error"] == "Waitlist code is required"
    print("test_validate_code_empty passed")

def test_validate_code_none():
    dao = WaitlistDAO()

    result = dao.validate_code(None)
    assert result["valid"] == False
    assert result["error"] == "Waitlist code is required"
    print("test_validate_code_none passed")

def test_mark_code_as_used():
    dao = WaitlistDAO()

    test_code = "MARK1234"
    test_username = "testuser123"

    dao.table.put_item(
        Item={
            "waitlistID": test_code,
            "email": "mark@example.com",
            "name": "Mark User",
            "used": False,
        }
    )

    success = dao.mark_code_as_used(test_code, test_username)
    assert success == True

    entry = dao.get_by_code(test_code)
    assert entry["used"] == True
    assert entry["usedBy"] == test_username
    assert "usedAt" in entry
    print("test_mark_code_as_used passed")

    dao.table.delete_item(Key={"waitlistID": test_code})

def test_get_by_code():
    dao = WaitlistDAO()

    test_code = "GET1234"
    dao.table.put_item(
        Item={
            "waitlistID": test_code,
            "email": "get@example.com",
            "name": "Get User",
            "used": False,
        }
    )

    entry = dao.get_by_code(test_code)
    assert entry is not None
    assert entry["waitlistID"] == test_code
    assert entry["email"] == "get@example.com"
    print("test_get_by_code passed")

    dao.table.delete_item(Key={"waitlistID": test_code})

def test_get_by_code_not_found():
    dao = WaitlistDAO()

    entry = dao.get_by_code("DOESNOTEXIST")
    assert entry is None
    print("test_get_by_code_not_found passed")

def run_all_tests():
    print("Running waitlist validation tests...\n")

    try:
        test_validate_code_success()
        test_validate_code_invalid()
        test_validate_code_already_used()
        test_validate_code_empty()
        test_validate_code_none()
        test_mark_code_as_used()
        test_get_by_code()
        test_get_by_code_not_found()

        print("\nAll tests passed!")
    except AssertionError as e:
        print(f"\nTest failed: {e}")
    except Exception as e:
        print(f"\nError running tests: {e}")

if __name__ == "__main__":
    run_all_tests()
