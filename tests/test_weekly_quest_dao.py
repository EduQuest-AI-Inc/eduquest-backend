import sys
import os
from datetime import datetime, timezone

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from models.weekly_quest import WeeklyQuest
from models.weekly_quest_item import WeeklyQuestItem
from data_access.weekly_quest_dao import WeeklyQuestDAO

def test_weekly_quest_crud():
    dao = WeeklyQuestDAO()

    # Create individual quest items
    quest1 = WeeklyQuestItem(
        individual_quest_id="iq-001",
        name="Intro to ML",
        skills="Python, Stats",
        week=1,
        status="not_started",
        description="Introduction to Machine Learning concepts"
    )

    quest2 = WeeklyQuestItem(
        individual_quest_id="iq-002",
        name="Data Cleaning",
        skills="Pandas, Data Analysis",
        week=2,
        status="not_started",
        description="Learn data cleaning techniques"
    )

    # Create weekly quest containing the list of individual quests
    weekly_quest = WeeklyQuest(
        quest_id="wq-001",
        student_id="stu123",
        period_id="period-001",
        quests=[quest1, quest2]
    )

    # -------Add-------
    # dao.add_weekly_quest(weekly_quest)

    # -------Get-------
    # result = dao.get_weekly_quest_by_id("wq-001")
    # print(result)

    # -------Update-------
    # dao.update_weekly_quest("wq-001", {"year": 2030})

    # -------Update Individual Quest-------
    # dao.update_individual_quest_in_weekly_quest("wq-001", "iq-001", {"status": "completed"})

    # -------Delete-------
    # dao.delete_weekly_quest("wq-001")

test_weekly_quest_crud()
