import pytest
from data_access.parent_dao import ParentDAO
from models.parent import Parent

_ID = "test-integration-parent-dao"


def _parent():
    return Parent(
        user_id=_ID,
        first_name="Test",
        last_name="Parent",
        email="test-integration-parent@example.com",
        password="hashed",
        role="parent",
        linked_student_ids=[],
    )


@pytest.mark.integration
def test_add_and_get_parent(supabase_required):
    dao = ParentDAO()
    try:
        dao.add_parent(_parent())
        result = dao.get_parent_by_id(_ID)
        assert result is not None
        assert result["user_id"] == _ID
    finally:
        dao.delete_parent(_ID)


@pytest.mark.integration
def test_get_linked_student_ids(supabase_required):
    dao = ParentDAO()
    try:
        dao.add_parent(_parent())
        dao.update_parent(_ID, {"linked_student_ids": ["s1", "s2"]})
        ids = dao.get_linked_student_ids(_ID)
        assert "s1" in ids
        assert "s2" in ids
    finally:
        dao.delete_parent(_ID)


@pytest.mark.integration
def test_update_parent(supabase_required):
    dao = ParentDAO()
    try:
        dao.add_parent(_parent())
        dao.update_parent(_ID, {"linked_student_ids": ["s99"]})
        result = dao.get_parent_by_id(_ID)
        assert "s99" in result["linked_student_ids"]
    finally:
        dao.delete_parent(_ID)


@pytest.mark.integration
def test_delete_parent(supabase_required):
    dao = ParentDAO()
    dao.add_parent(_parent())
    dao.delete_parent(_ID)
    assert dao.get_parent_by_id(_ID) is None
