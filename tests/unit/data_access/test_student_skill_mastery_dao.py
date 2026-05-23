from unittest.mock import MagicMock, patch

import pytest

from models.student_skill_mastery import MASTERY_CUTOFF


def _build_dao():
    """Construct a DAO with the Supabase client patched out."""
    with patch("data_access.base_dao.get_admin_supabase_client", return_value=MagicMock()):
        from data_access.student_skill_mastery_dao import StudentSkillMasteryDAO
        return StudentSkillMasteryDAO()


@pytest.mark.unit
def test_upsert_score_flips_mastered_at_threshold():
    dao = _build_dao()
    captured = {}

    def fake_upsert(item):
        captured.update(item)
        return item

    dao._upsert = fake_upsert  # type: ignore[assignment]

    row = dao.upsert_score(
        student_id="s1",
        period_id="p1",
        skill_name="loops",
        score=0.85,
        threshold=0.8,
    )

    assert row.mastered is True
    assert captured["mastered"] is True
    assert captured["score"] == 0.85
    assert captured["skill_name"] == "loops"


@pytest.mark.unit
def test_upsert_score_below_threshold_not_mastered():
    dao = _build_dao()
    dao._upsert = MagicMock()  # type: ignore[assignment]

    row = dao.upsert_score(
        student_id="s1",
        period_id="p1",
        skill_name="loops",
        score=0.6,
        threshold=0.8,
    )

    assert row.mastered is False
    dao._upsert.assert_called_once()


@pytest.mark.unit
def test_upsert_score_uses_default_cutoff():
    dao = _build_dao()
    dao._upsert = MagicMock()  # type: ignore[assignment]

    row = dao.upsert_score(
        student_id="s1",
        period_id="p1",
        skill_name="loops",
        score=MASTERY_CUTOFF,
    )

    # Exactly at cutoff counts as mastered
    assert row.mastered is True


@pytest.mark.unit
def test_bulk_upsert_skips_empty():
    dao = _build_dao()
    dao._execute = MagicMock()  # type: ignore[assignment]
    dao.bulk_upsert([])
    dao._execute.assert_not_called()


@pytest.mark.unit
def test_get_for_student_uses_composite_filter():
    dao = _build_dao()
    fake_response = MagicMock()
    fake_response.data = [
        {
            "student_id": "s1",
            "period_id": "p1",
            "skill_name": "loops",
            "score": 0.5,
            "mastered": False,
        }
    ]
    dao._execute = MagicMock(return_value=fake_response)  # type: ignore[assignment]

    rows = dao.get_for_student("s1", "p1")

    assert len(rows) == 1
    assert rows[0].skill_name == "loops"
    dao._execute.assert_called_once()


@pytest.mark.unit
def test_delete_for_student_period():
    dao = _build_dao()
    dao._delete = MagicMock()  # type: ignore[assignment]
    dao.delete_for_student_period("s1", "p1")
    dao._delete.assert_called_once_with({"student_id": "s1", "period_id": "p1"})
