import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data_access.session_dao import SessionDAO
from models.session import Session

def test_crud_operations():
    dao = SessionDAO()

    session = Session(
        auth_token="test_token_001",
        user_id="test_user_123",
        role="student"
    )

    # -------Add-------
    # dao.add_session(session)

    # -------Update-------
    # dao.update_session(
    #     auth_token=session.auth_token,
    #     user_id=session.user_id,
    #     updates={"role": "teacher"}
    # )

    # -------Get-------
    # result = dao.get_sessions_by_auth_token("test_token_001")
    # print(result)

    # -------Delete-------
    # dao.delete_session(session.auth_token, session.user_id)
    # final = dao.get_sessions_by_auth_token("test_token_001")
    # assert not any(s["user_id"] == "test_user_123" for s in final)

test_crud_operations()
