import sys
import os
from datetime import datetime, timezone

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data_access.weekly_quest_dao import WeeklyQuestDAO
from models.weekly_quest import WeeklyQuest

def test_crud_operations():
    dao = WeeklyQuestDAO()

    created_at = datetime.now(timezone.utc).isoformat()

    weekly_quest = WeeklyQuest(
        student_id="stu123",
        week=21,
        year=2025,
        created_at=created_at,
        last_updated_at=created_at,
        quests=["quest001", "quest002"]
    )

    # -------Add-------
    # dao.add_weekly_quest(weekly_quest)

    # -------Update-------
    # dao.update_weekly_quest("stu123", "2025-05-19T15:55:37.879411+00:00", {"week": 22, "quests": ["quest003"]})

    # -------Get-------
    # result = dao.get_weekly_quests_by_student("stu123")
    # print(result)

    # -------Delete-------
    dao.delete_weekly_quest("stu123", "2025-05-19T15:55:37.879411+00:00")

test_crud_operations()
