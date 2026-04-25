import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

import json
from mock_course_data import data

from data_access.period_dao import PeriodDAO
from models.period import Period

def test_crud_operations() -> None:
    dao = PeriodDAO()

    period = Period(
        period_id="per001",
        owner_id="teach001",
        user_id="teach001",
        vector_store_id="vs_789",
        name=json.dumps(data, indent=2),
    )

    # -------Add-------
    # dao.add_period(period)

    # -------Update-------
    # dao.update_period("per001", {"name": "Advanced Math"})

    # -------Get-------
    # result = dao.get_period_by_id("per001")
    # print(result)

    # -------Delete-------
    # dao.delete_period("per001")

test_crud_operations()
