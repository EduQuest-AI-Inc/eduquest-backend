import os
import pytest


@pytest.fixture(scope="session")
def supabase_required():
    if os.environ.get("SUPABASE_SERVICE_ROLE_KEY") == "test-service-role-key":
        pytest.skip("Integration tests require a real SUPABASE_SERVICE_ROLE_KEY")


@pytest.fixture
def db_period(supabase_required):
    from data_access.period_dao import PeriodDAO
    from models.period import Period
    dao = PeriodDAO()
    p = Period(
        period_id="test-integration-shared-period",
        owner_id="test-integration-owner",
        name="Integration Test Period",
        vector_store_id="vs-test",
    )
    dao.add_period(p)
    yield p
    dao.delete_period(p.period_id)


@pytest.fixture
def db_user(supabase_required):
    from data_access.user_dao import UserDAO
    from models.user import User
    dao = UserDAO()
    u = User(
        user_id="test-integration-shared-user",
        first_name="Test",
        last_name="User",
        email="test-integration@eduquestai.org",
        password="hashed",
        role="student",
    )
    dao.delete(u.user_id)
    dao.add_user(u)
    yield u
    dao.delete(u.user_id)
