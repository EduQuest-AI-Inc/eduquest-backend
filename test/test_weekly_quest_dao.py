import sys
import os
from datetime import datetime, timezone

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from models.weekly_quest import WeeklyQuest
from models.individual_quest import IndividualQuest
from data_access.weekly_quest_dao import WeeklyQuestDAO

def test_weekly_quest_crud():
    dao = WeeklyQuestDAO()

    quest1 = IndividualQuest(
        week=1,
        description="Intro to ML",
        grade="A",
        feedback="Great job!",
        skills="Python, Stats",
        due_date="2025-05-30"
    )

    quest2 = IndividualQuest(
        week=1,
        description="Data Cleaning",
        grade="B+",
        feedback="Could be cleaner",
        skills="Pandas",
        due_date="2025-06-06"
    )

    weekly_quest = WeeklyQuest(
        weekly_quest_id="wq-001",
        student_id="stu123",
        year=2025,
        quests=[quest1, quest2]
    )

    # -------Add-------
    # dao.add_weekly_quest(weekly_quest)

    # -------Get-------
    # result = dao.get_weekly_quest_by_id("wq-001")
    # print(result)

    # -------Update-------
    dao.update_weekly_quest("wq-001", {"year": 2030})

    # -------Delete-------
    # dao.delete_weekly_quest("wq-001", weekly_quest.created_at)

test_weekly_quest_crud()
