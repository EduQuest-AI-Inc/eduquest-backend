import os
import pytest

# Integration fixture conventions:
#   1. Always delete-before-insert for any fixture using a fixed ID — leftover rows
#      from crashed runs cause duplicate-key ERRORs across all dependent tests.
#   2. Print at the start of setup so fixture failures are locatable in pytest output.


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
    print(f"\n[fixture] db_period setup: pre-deleting {p.period_id}")
    dao.delete_period(p.period_id)
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
    print(f"\n[fixture] db_user setup: pre-deleting {u.user_id}")
    dao.delete(u.user_id)
    dao.add_user(u)
    yield u
    dao.delete(u.user_id)
