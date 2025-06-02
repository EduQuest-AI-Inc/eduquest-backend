import sys
import os
from datetime import datetime, timezone

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data_access.student_dao import StudentDAO
from models.student import Student

def test_crud_operations():

    dao = StudentDAO()

    student = Student(
        student_id="stu456",
        first_name="Bob",
        last_name="Tanaka",
        email="bob@example.com",
        enrollments=["CS102", "MATH300"],
        grade=4,
        strenth="Math",
        weakness="Writing",
        interest="Robotics",
        learning_style="Visual",
        long_term_goal=[{"period_id": "p2", "goals": "Graduate"}],
        quests=[{"period_id": "p2", "quest_id": "q2"}],
        last_login=datetime.now(timezone.utc).isoformat(),
        password="securepass"
    )

    # -------Add-------
    # dao.add_student(student)

    # -------Update-------
    # dao.update_student("stu456", {"grade": 5})

    # -------Get-------
    # result = dao.get_student_by_id("stu456")
    # print(result)

    # -------Delete-------
    dao.delete_student("stu456")


test_crud_operations()
