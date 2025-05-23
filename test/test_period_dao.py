import sys
import os
import json
from mock_course_data import data

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data_access.period_dao import PeriodDAO
from models.period import Period

def test_crud_operations():
    dao = PeriodDAO()

    period = Period(
        period_id="per001",
        initial_conversation_assistant_id="conv_init_123",
        update_assistant_id="conv_upd_456",
        teacher_id="teach001",
        vector_store_id="vs_789",
        course= json.dumps(data, indent=2)
    )

    # -------Add-------
    # dao.add_period(period)

    # -------Update-------
    # dao.update_period("per001", {"course": "Advanced Math", "update_assistant_id": "conv_upd_999"})

    # -------Get-------
    # result = dao.get_period_by_id("per001")
    # print(result)

    # -------Delete-------
    # dao.delete_period("per001")

test_crud_operations()
