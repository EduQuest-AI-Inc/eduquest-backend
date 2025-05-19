import sys
import os

# Ensure the root project folder is in the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data_access.enrollment_dao import EnrollmentDAO
from models.enrollment import Enrollment
from datetime import datetime, timezone

def test_crud_operations():
    dao = EnrollmentDAO()

    enrollment = Enrollment(
        class_id="CS101",
        student_id="stu_test",
        semester="TestSemester",
        enrolled_at="2025-05-17T13:24:53.812345+00:00"
    )

    # -------Add-------
    # dao.add_enrollment(enrollment)

    # -------Update-------
    # dao.update_enrollment(
    #     class_id=enrollment.class_id,
    #     enrolled_at=enrollment.enrolled_at,
    #     updates={"semester": "Hello"}
    # )

    # -------Get-------
    # response = dao.get_enrollments_by_class("CS101")
    # print(response)

    # -------Delete-------
    # dao.delete_enrollment(enrollment.class_id, enrollment.enrolled_at)
    # final = dao.get_enrollments_by_class("CS101")
    # assert not any(e.student_id == "stu_test" for e in final)


test_crud_operations()
