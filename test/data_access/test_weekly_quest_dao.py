import os
import sys
import uuid
import pytest
from datetime import datetime, timezone

# Make backend importable
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from data_access.weekly_quest_dao import WeeklyQuestDAO
from models.weekly_quest import WeeklyQuest


@pytest.mark.integration
class TestWeeklyQuestDAO:
    """Test suite for WeeklyQuestDAO with new structure (no nested quests)."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.dao = WeeklyQuestDAO()
        self.test_quest_id = f"wq_test_{uuid.uuid4().hex[:8]}"
        self.test_student_id = f"stu_test_{uuid.uuid4().hex[:8]}"
        self.test_period_id = f"period_test_{uuid.uuid4().hex[:8]}"
    
    def teardown_method(self):
        """Clean up test data."""
        try:
            # Query to get all items with this quest_id to delete them
            response = self.dao.table.query(
                KeyConditionExpression=self.dao.key("quest_id").eq(self.test_quest_id)
            )
            items = response.get("Items", [])
            for item in items:
                self.dao.delete_weekly_quest(self.test_quest_id, item["last_updated_at"])
        except Exception:
            pass  # Ignore cleanup errors
    
    def _get_quest_last_updated_at(self, quest_id: str) -> str:
        """Helper method to get the last_updated_at value for a quest."""
        response = self.dao.table.query(
            KeyConditionExpression=self.dao.key("quest_id").eq(quest_id),
            ScanIndexForward=False  # Get most recent first
        )
        items = response.get("Items", [])
        if items:
            return items[0]["last_updated_at"]
        return None
    
    def test_add_weekly_quest(self):
        """Test adding a weekly quest (metadata only, no nested quests)."""
        weekly_quest = WeeklyQuest(
            quest_id=self.test_quest_id,
            student_id=self.test_student_id,
            period_id=self.test_period_id,
            student_period_key=f"{self.test_student_id}#{self.test_period_id}"
        )
        
        # Act
        self.dao.add_weekly_quest(weekly_quest)
        
        # Get the last_updated_at value
        last_updated_at = self._get_quest_last_updated_at(self.test_quest_id)
        assert last_updated_at is not None
        
        # Assert
        result = self.dao.get_weekly_quest_by_id(self.test_quest_id, last_updated_at)
        assert result is not None
        assert result.quest_id == self.test_quest_id
        assert result.student_id == self.test_student_id
        assert result.period_id == self.test_period_id
        assert result.student_period_key == f"{self.test_student_id}#{self.test_period_id}"
    
    def test_get_weekly_quest_by_id(self):
        """Test retrieving a weekly quest by ID."""
        # Arrange
        weekly_quest = WeeklyQuest(
            quest_id=self.test_quest_id,
            student_id=self.test_student_id,
            period_id=self.test_period_id,
            student_period_key=f"{self.test_student_id}#{self.test_period_id}",
            year=2025,
            semester="Fall 2025"
        )
        self.dao.add_weekly_quest(weekly_quest)
        
        # Get the last_updated_at value
        last_updated_at = self._get_quest_last_updated_at(self.test_quest_id)
        assert last_updated_at is not None
        
        # Act
        result = self.dao.get_weekly_quest_by_id(self.test_quest_id, last_updated_at)
        
        # Assert
        assert result is not None
        assert result.quest_id == self.test_quest_id
        assert result.student_id == self.test_student_id
        assert result.period_id == self.test_period_id
        assert result.year == 2025
        assert result.semester == "Fall 2025"
    
    def test_get_weekly_quest_by_id_not_found(self):
        """Test retrieving a non-existent weekly quest returns None."""
        # Act - use a fake last_updated_at since quest doesn't exist
        fake_timestamp = datetime.now(timezone.utc).isoformat()
        result = self.dao.get_weekly_quest_by_id("non_existent_quest_id", fake_timestamp)
        
        # Assert
        assert result is None
    
    def test_update_weekly_quest(self):
        """Test updating weekly quest metadata."""
        # Arrange
        weekly_quest = WeeklyQuest(
            quest_id=self.test_quest_id,
            student_id=self.test_student_id,
            period_id=self.test_period_id,
            student_period_key=f"{self.test_student_id}#{self.test_period_id}",
            year=2025
        )
        self.dao.add_weekly_quest(weekly_quest)
        
        # Get the last_updated_at value before update
        last_updated_at = self._get_quest_last_updated_at(self.test_quest_id)
        assert last_updated_at is not None
        
        # Act
        self.dao.update_weekly_quest(self.test_quest_id, last_updated_at, {
            "year": 2026,
            "semester": "Spring 2026"
        })
        
        # Assert - use the same last_updated_at since it's the sort key and cannot change
        result = self.dao.get_weekly_quest_by_id(self.test_quest_id, last_updated_at)
        assert result.year == 2026
        assert result.semester == "Spring 2026"
        assert result.last_updated_at is not None
        assert result.last_updated_at == last_updated_at
    
    def test_get_weekly_quest_by_student_and_period(self):
        """Test retrieving weekly quest by student_id and period_id using GSI."""
        # Arrange
        weekly_quest = WeeklyQuest(
            quest_id=self.test_quest_id,
            student_id=self.test_student_id,
            period_id=self.test_period_id,
            student_period_key=f"{self.test_student_id}#{self.test_period_id}"
        )
        self.dao.add_weekly_quest(weekly_quest)
        
        # Act - with retry logic for eventual consistency
        import time
        result = None
        for attempt in range(5):
            result = self.dao.get_weekly_quest_by_student_and_period(
                self.test_student_id, 
                self.test_period_id
            )
            if result:
                break
            time.sleep(0.5)
        
        # Assert
        assert result is not None
        assert result.quest_id == self.test_quest_id
        assert result.student_id == self.test_student_id
        assert result.period_id == self.test_period_id
    
    def test_get_quests_by_student_and_period(self):
        """Test retrieving all weekly quests for a student and period."""
        # Arrange
        weekly_quest = WeeklyQuest(
            quest_id=self.test_quest_id,
            student_id=self.test_student_id,
            period_id=self.test_period_id,
            student_period_key=f"{self.test_student_id}#{self.test_period_id}"
        )
        self.dao.add_weekly_quest(weekly_quest)
        
        # Act
        results = self.dao.get_quests_by_student_and_period(
            self.test_student_id,
            self.test_period_id
        )
        
        # Assert
        assert isinstance(results, list)
        assert len(results) >= 1
        assert any(r.quest_id == self.test_quest_id for r in results)
    
    def test_delete_weekly_quest(self):
        """Test deleting a weekly quest."""
        # Arrange
        weekly_quest = WeeklyQuest(
            quest_id=self.test_quest_id,
            student_id=self.test_student_id,
            period_id=self.test_period_id,
            student_period_key=f"{self.test_student_id}#{self.test_period_id}"
        )
        self.dao.add_weekly_quest(weekly_quest)
        
        # Get the last_updated_at value
        last_updated_at = self._get_quest_last_updated_at(self.test_quest_id)
        assert last_updated_at is not None
        
        # Act
        self.dao.delete_weekly_quest(self.test_quest_id, last_updated_at)
        
        # Assert - verify it's deleted
        result = self.dao.get_weekly_quest_by_id(self.test_quest_id, last_updated_at)
        assert result is None
    
    def test_weekly_quest_metadata_only(self):
        """Test that weekly quest only stores metadata, not nested quests."""
        # Arrange
        weekly_quest = WeeklyQuest(
            quest_id=self.test_quest_id,
            student_id=self.test_student_id,
            period_id=self.test_period_id,
            student_period_key=f"{self.test_student_id}#{self.test_period_id}"
        )
        
        # Act
        item = weekly_quest.to_item()
        
        # Assert - verify no 'quests' field exists
        assert 'quests' not in item
        assert 'quest_id' in item
        assert 'student_id' in item
        assert 'period_id' in item
    
    def test_multiple_weekly_quests_same_student_different_periods(self):
        """Test that a student can have multiple weekly quests for different periods."""
        # Arrange
        period_id_2 = f"period_test_{uuid.uuid4().hex[:8]}"
        quest_id_2 = f"wq_test_{uuid.uuid4().hex[:8]}"
        
        weekly_quest_1 = WeeklyQuest(
            quest_id=self.test_quest_id,
            student_id=self.test_student_id,
            period_id=self.test_period_id,
            student_period_key=f"{self.test_student_id}#{self.test_period_id}"
        )
        
        weekly_quest_2 = WeeklyQuest(
            quest_id=quest_id_2,
            student_id=self.test_student_id,
            period_id=period_id_2,
            student_period_key=f"{self.test_student_id}#{period_id_2}"
        )
        
        # Act
        self.dao.add_weekly_quest(weekly_quest_1)
        self.dao.add_weekly_quest(weekly_quest_2)
        
        # Assert
        result_1 = self.dao.get_weekly_quest_by_student_and_period(
            self.test_student_id, 
            self.test_period_id
        )
        result_2 = self.dao.get_weekly_quest_by_student_and_period(
            self.test_student_id, 
            period_id_2
        )
        
        assert result_1 is not None
        assert result_1.quest_id == self.test_quest_id
        assert result_2 is not None
        assert result_2.quest_id == quest_id_2
        
        # Cleanup
        try:
            last_updated_at_2 = self._get_quest_last_updated_at(quest_id_2)
            if last_updated_at_2:
                self.dao.delete_weekly_quest(quest_id_2, last_updated_at_2)
        except Exception:
            pass