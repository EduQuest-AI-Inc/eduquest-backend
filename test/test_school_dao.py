import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data_access.school_dao import SchoolDAO
from models.school import School

def test_crud_operations():
    dao = SchoolDAO()

    school = School(
        school_id="school001",
        school_name="OpenAI Academy",
    )

    # -------Add-------
    # dao.add_school(school)

    # -------Update-------
    # dao.update_school("school001", {"school_name": "OpenAI Advanced Academy"})

    # -------Get-------
    # result = dao.get_school_by_id("school001")
    # print(result)

    # -------Delete-------
    dao.delete_school("school001")

test_crud_operations()
