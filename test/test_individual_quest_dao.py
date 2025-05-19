import sys
import os
from datetime import datetime, timezone

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data_access.individual_quest_dao import IndividualQuestDAO
from models.individual_quest import IndividualQuest

def test_crud_operations():
    dao = IndividualQuestDAO()

    created_at = datetime.now(timezone.utc).isoformat()

    quest = IndividualQuest(
        quest_id="quest123",
        Description="Solve graph traversal problem",
        Grade="A",
        Feedback="Well done!",
        Skills="Graphs, BFS, DFS",
        created_at=created_at
    )

    # -------Add-------
    # dao.add_individual_quest(quest)

    # -------Update-------
    # dao.update_individual_quest("quest123", "2025-05-19T15:59:50.898856+00:00", {"Grade": "A+", "Feedback": "Excellent work!"})

    # -------Get-------
    # result = dao.get_individual_quest("quest123")
    # print(result)

    # -------Delete-------
    dao.delete_individual_quest("quest123", "2025-05-19T15:59:50.898856+00:00")

test_crud_operations()
