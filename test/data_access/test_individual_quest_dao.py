import os
import sys
import uuid
import pytest
from datetime import datetime, timezone

# Make backend importable
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from data_access.individual_quest_dao import IndividualQuestDAO
from models.individual_quest import IndividualQuest


@pytest.mark.integration
class TestIndividualQuestDAO:
    """Test suite for IndividualQuestDAO with GSI support."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.dao = IndividualQuestDAO()
        self.test_quest_id = f"wq_test_{uuid.uuid4().hex[:8]}"
        self.test_student_id = f"stu_test_{uuid.uuid4().hex[:8]}"
        self.test_period_id = f"period_test_{uuid.uuid4().hex[:8]}"
        self.test_individual_quest_ids = []
    
    def teardown_method(self):
        """Clean up test data."""
        for individual_quest_id in self.test_individual_quest_ids:
            try:
                self.dao.delete_individual_quest(individual_quest_id)
            except Exception:
                pass  # Ignore cleanup errors
    
    def test_add_individual_quest(self):
        """Test adding an individual quest."""
        individual_quest_id = f"iq_test_{uuid.uuid4().hex[:8]}"
        self.test_individual_quest_ids.append(individual_quest_id)
        
        individual_quest = IndividualQuest(
            individual_quest_id=individual_quest_id,
            quest_id=self.test_quest_id,
            student_id=self.test_student_id,
            period_id=self.test_period_id,
            description="Test Quest",
            skills="Python, Testing",
            week=1,
            instructions="Complete this quest",
            rubric={"criteria": "test"},
            status="not_started"
        )
        
        # Act
        self.dao.add_individual_quest(individual_quest)
        
        # Assert
        result = self.dao.get_individual_quest_by_id(individual_quest_id)
        assert result is not None
        assert result["individual_quest_id"] == individual_quest_id
        assert result["quest_id"] == self.test_quest_id
        assert result["student_id"] == self.test_student_id
        assert result["description"] == "Test Quest"
        assert result["week"] == 1
    
    def test_get_individual_quest_by_id(self):
        """Test retrieving an individual quest by ID."""
        # Arrange
        individual_quest_id = f"iq_test_{uuid.uuid4().hex[:8]}"
        self.test_individual_quest_ids.append(individual_quest_id)
        
        individual_quest = IndividualQuest(
            individual_quest_id=individual_quest_id,
            quest_id=self.test_quest_id,
            student_id=self.test_student_id,
            period_id=self.test_period_id,
            description="Test Quest",
            skills="Python",
            week=1,
            instructions="Instructions",
            rubric={},
            status="not_started"
        )
        self.dao.add_individual_quest(individual_quest)
        
        # Act
        result = self.dao.get_individual_quest_by_id(individual_quest_id)
        
        # Assert
        assert result is not None
        assert result["individual_quest_id"] == individual_quest_id
        assert result["quest_id"] == self.test_quest_id
    
    def test_get_individual_quest_by_id_not_found(self):
        """Test retrieving a non-existent individual quest returns None."""
        # Act
        result = self.dao.get_individual_quest_by_id("non_existent_quest_id")
        
        # Assert
        assert result is None
    
    def test_update_individual_quest(self):
        """Test updating an individual quest."""
        # Arrange
        individual_quest_id = f"iq_test_{uuid.uuid4().hex[:8]}"
        self.test_individual_quest_ids.append(individual_quest_id)
        
        individual_quest = IndividualQuest(
            individual_quest_id=individual_quest_id,
            quest_id=self.test_quest_id,
            student_id=self.test_student_id,
            period_id=self.test_period_id,
            description="Original Description",
            skills="Python",
            week=1,
            instructions="Original Instructions",
            rubric={},
            status="not_started"
        )
        self.dao.add_individual_quest(individual_quest)
        
        # Act
        self.dao.update_individual_quest(individual_quest_id, {
            "description": "Updated Description",
            "status": "in_progress"
        })
        
        # Assert
        result = self.dao.get_individual_quest_by_id(individual_quest_id)
        assert result["description"] == "Updated Description"
        assert result["status"] == "in_progress"
        assert result["last_updated_at"] is not None
    
    def test_get_quests_by_quest_id_gsi(self):
        """Test retrieving individual quests by quest_id using GSI."""
        # Arrange
        quest_id = self.test_quest_id
        individual_quest_ids = []
        
        for week in range(1, 4):
            individual_quest_id = f"iq_test_{uuid.uuid4().hex[:8]}"
            individual_quest_ids.append(individual_quest_id)
            self.test_individual_quest_ids.append(individual_quest_id)
            
            individual_quest = IndividualQuest(
                individual_quest_id=individual_quest_id,
                quest_id=quest_id,
                student_id=self.test_student_id,
                period_id=self.test_period_id,
                description=f"Quest Week {week}",
                skills="Python",
                week=week,
                instructions="Instructions",
                rubric={},
                status="not_started"
            )
            self.dao.add_individual_quest(individual_quest)
        
        # Act - with retry for eventual consistency
        import time
        results = []
        for attempt in range(5):
            results = self.dao.get_quests_by_quest_id_gsi(quest_id)
            if len(results) >= 3:
                break
            time.sleep(0.5)
        
        # Assert
        assert len(results) >= 3
        result_quest_ids = {r["individual_quest_id"] for r in results}
        assert all(iq_id in result_quest_ids for iq_id in individual_quest_ids)
        assert all(r["quest_id"] == quest_id for r in results)
    
    def test_get_quests_by_student(self):
        """Test retrieving all individual quests for a student."""
        # Arrange
        individual_quest_id = f"iq_test_{uuid.uuid4().hex[:8]}"
        self.test_individual_quest_ids.append(individual_quest_id)
        
        individual_quest = IndividualQuest(
            individual_quest_id=individual_quest_id,
            quest_id=self.test_quest_id,
            student_id=self.test_student_id,
            period_id=self.test_period_id,
            description="Test Quest",
            skills="Python",
            week=1,
            instructions="Instructions",
            rubric={},
            status="not_started"
        )
        self.dao.add_individual_quest(individual_quest)
        
        # Act
        results = self.dao.get_quests_by_student(self.test_student_id)
        
        # Assert
        assert isinstance(results, list)
        assert len(results) >= 1
        assert any(r["individual_quest_id"] == individual_quest_id for r in results)
        assert all(r["student_id"] == self.test_student_id for r in results)
    
    def test_get_quests_by_student_and_period(self):
        """Test retrieving individual quests by student_id and period_id."""
        # Arrange
        individual_quest_id = f"iq_test_{uuid.uuid4().hex[:8]}"
        self.test_individual_quest_ids.append(individual_quest_id)
        
        individual_quest = IndividualQuest(
            individual_quest_id=individual_quest_id,
            quest_id=self.test_quest_id,
            student_id=self.test_student_id,
            period_id=self.test_period_id,
            description="Test Quest",
            skills="Python",
            week=1,
            instructions="Instructions",
            rubric={},
            status="not_started"
        )
        self.dao.add_individual_quest(individual_quest)
        
        # Act
        results = self.dao.get_quests_by_student_and_period(
            self.test_student_id,
            self.test_period_id
        )
        
        # Assert
        assert isinstance(results, list)
        assert len(results) >= 1
        assert any(r["individual_quest_id"] == individual_quest_id for r in results)
        assert all(r["student_id"] == self.test_student_id and 
                  r["period_id"] == self.test_period_id for r in results)
    
    def test_update_quest_grade_and_feedback(self):
        """Test updating quest grade and feedback."""
        # Arrange
        individual_quest_id = f"iq_test_{uuid.uuid4().hex[:8]}"
        self.test_individual_quest_ids.append(individual_quest_id)
        
        individual_quest = IndividualQuest(
            individual_quest_id=individual_quest_id,
            quest_id=self.test_quest_id,
            student_id=self.test_student_id,
            period_id=self.test_period_id,
            description="Test Quest",
            skills="Python",
            week=1,
            instructions="Instructions",
            rubric={},
            status="not_started"
        )
        self.dao.add_individual_quest(individual_quest)
        
        # Act
        self.dao.update_quest_grade_and_feedback(
            individual_quest_id,
            '{"overall_score": "A", "detailed_grade": {}}',
            "Great work!"
        )
        
        # Assert
        result = self.dao.get_individual_quest_by_id(individual_quest_id)
        assert result["grade"] == '{"overall_score": "A", "detailed_grade": {}}'
        assert result["feedback"] == "Great work!"
        assert result["status"] == "completed"
    
    def test_update_quest_status(self):
        """Test updating quest status."""
        # Arrange
        individual_quest_id = f"iq_test_{uuid.uuid4().hex[:8]}"
        self.test_individual_quest_ids.append(individual_quest_id)
        
        individual_quest = IndividualQuest(
            individual_quest_id=individual_quest_id,
            quest_id=self.test_quest_id,
            student_id=self.test_student_id,
            period_id=self.test_period_id,
            description="Test Quest",
            skills="Python",
            week=1,
            instructions="Instructions",
            rubric={},
            status="not_started"
        )
        self.dao.add_individual_quest(individual_quest)
        
        # Act
        self.dao.update_quest_status(individual_quest_id, "in_progress")
        
        # Assert
        result = self.dao.get_individual_quest_by_id(individual_quest_id)
        assert result["status"] == "in_progress"
    
    def test_delete_individual_quest(self):
        """Test deleting an individual quest."""
        # Arrange
        individual_quest_id = f"iq_test_{uuid.uuid4().hex[:8]}"
        
        individual_quest = IndividualQuest(
            individual_quest_id=individual_quest_id,
            quest_id=self.test_quest_id,
            student_id=self.test_student_id,
            period_id=self.test_period_id,
            description="Test Quest",
            skills="Python",
            week=1,
            instructions="Instructions",
            rubric={},
            status="not_started"
        )
        self.dao.add_individual_quest(individual_quest)
        
        # Act
        self.dao.delete_individual_quest(individual_quest_id)
        
        # Assert
        result = self.dao.get_individual_quest_by_id(individual_quest_id)
        assert result is None
    
    def test_get_quests_by_quest_id_scan(self):
        """Test retrieving individual quests by quest_id using scan (fallback)."""
        # Arrange
        quest_id = self.test_quest_id
        individual_quest_id = f"iq_test_{uuid.uuid4().hex[:8]}"
        self.test_individual_quest_ids.append(individual_quest_id)
        
        individual_quest = IndividualQuest(
            individual_quest_id=individual_quest_id,
            quest_id=quest_id,
            student_id=self.test_student_id,
            period_id=self.test_period_id,
            description="Test Quest",
            skills="Python",
            week=1,
            instructions="Instructions",
            rubric={},
            status="not_started"
        )
        self.dao.add_individual_quest(individual_quest)
        
        # Act
        results = self.dao.get_quests_by_quest_id(quest_id)
        
        # Assert
        assert isinstance(results, list)
        assert len(results) >= 1
        assert any(r["individual_quest_id"] == individual_quest_id for r in results)
        assert all(r["quest_id"] == quest_id for r in results)
    
    def test_multiple_quests_same_quest_id(self):
        """Test that multiple individual quests can share the same quest_id."""
        # Arrange
        quest_id = self.test_quest_id
        individual_quest_ids = []
        
        for week in range(1, 4):
            individual_quest_id = f"iq_test_{uuid.uuid4().hex[:8]}"
            individual_quest_ids.append(individual_quest_id)
            self.test_individual_quest_ids.append(individual_quest_id)
            
            individual_quest = IndividualQuest(
                individual_quest_id=individual_quest_id,
                quest_id=quest_id,
                student_id=self.test_student_id,
                period_id=self.test_period_id,
                description=f"Quest Week {week}",
                skills="Python",
                week=week,
                instructions="Instructions",
                rubric={},
                status="not_started"
            )
            self.dao.add_individual_quest(individual_quest)
        
        # Act - with retry for eventual consistency
        import time
        results = []
        for attempt in range(5):
            results = self.dao.get_quests_by_quest_id_gsi(quest_id)
            if len(results) >= 3:
                break
            time.sleep(0.5)
        
        # Assert
        assert len(results) >= 3
        # Filter results that have quest_id matching and have week attribute
        valid_results = [r for r in results if r.get("quest_id") == quest_id and "week" in r]
        weeks = sorted([r["week"] for r in valid_results])
        assert len(weeks) >= 3
        assert all(w in weeks for w in [1, 2, 3])