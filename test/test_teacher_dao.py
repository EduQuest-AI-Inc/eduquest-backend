import sys
import os
from datetime import datetime, timezone

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data_access.teacher_dao import TeacherDAO
from models.teacher import Teacher

def test_crud_operations():
    dao = TeacherDAO()

    now = datetime.now(timezone.utc).isoformat()

    teacher = Teacher(
        teacher_id="teach001",
        first_name="Bob",
        last_name="Smith",
        last_login=now,
        password="securePass123"
    )

    # -------Add-------
    # dao.add_teacher(teacher)

    # -------Update-------
    # dao.update_teacher("teach001", {"password": "newSecurePass456", "last_login": datetime.now(timezone.utc).isoformat()})

    # -------Get-------
    # result = dao.get_teacher_by_id("teach001")
    # print(result)

    # -------Delete-------
    # dao.delete_teacher("teach001")

test_crud_operations()
