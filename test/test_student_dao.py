import sys
import os
from datetime import datetime, timezone

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data_access.student_dao import StudentDAO
from models.student import Student

def test_crud_operations():
    dao = StudentDAO()

    student = Student(
        student_id="stu123",
        first_name="Alice",
        last_name="Watanabe",
        enrollments=["CS101", "MATH200"],
        grade=3,
        strenth="Logic",
        weakness="Theory",
        interest="AI",
        learning_style="Hands-on",
        long_term_goal="ML Researcher",
        last_login=datetime.now(timezone.utc).isoformat(),
        password="password"
    )

    # -------Add-------
    # dao.add_student(student)

    # -------Update-------
    # dao.update_student("stu123", "2025-05-19T15:33:15.671818+00:00", {"grade": 5, "interest": "AI & Robotics"})

    # -------Get-------
    # result = dao.get_student_by_id("stu123")
    # print(result)

    # -------Delete-------
    dao.delete_student("stu123", "2025-05-19T18:23:22.849078+00:00")


test_crud_operations()
