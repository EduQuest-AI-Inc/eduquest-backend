import os
import sys
import uuid
import pytest
from datetime import datetime, timezone

# Make backend importable - add root directory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from routes.quest.quest_service import QuestService
from data_access.weekly_quest_dao import WeeklyQuestDAO
from data_access.individual_quest_dao import IndividualQuestDAO
from models.weekly_quest import WeeklyQuest
from models.individual_quest import IndividualQuest


@pytest.mark.integration
class TestQuestService:
    """Test suite for QuestService with new structure (no WeeklyQuestItem)."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.service = QuestService()
        self.weekly_quest_dao = WeeklyQuestDAO()
        self.individual_quest_dao = IndividualQuestDAO()
        self.test_quest_id = f"wq_test_{uuid.uuid4().hex[:8]}"
        self.test_student_id = f"stu_test_{uuid.uuid4().hex[:8]}"
        self.test_period_id = f"period_test_{uuid.uuid4().hex[:8]}"
        self.test_individual_quest_ids = []
    
    def teardown_method(self):
        """Clean up test data."""
        # Delete individual quests
        for individual_quest_id in self.test_individual_quest_ids:
            try:
                self.individual_quest_dao.delete_individual_quest(individual_quest_id)
            except Exception:
                pass
        
        # Delete weekly quest
        try:
            self.weekly_quest_dao.delete_weekly_quest(self.test_quest_id)
        except Exception:
            pass
    
    def test_save_schedule_to_weekly_quests(self):
        """Test saving schedule creates weekly quest metadata and individual quests."""
        # Arrange
        schedule_data = {
            "list_of_quests": [
                {"Name": "Quest 1", "Skills": "Python", "Week": 1},
                {"Name": "Quest 2", "Skills": "JavaScript", "Week": 2},
                {"Name": "Quest 3", "Skills": "SQL", "Week": 3}
            ]
        }
        
        # Act
        result = self.service.save_schedule_to_weekly_quests(
            schedule_data,
            self.test_student_id,
            self.test_period_id
        )
        
        # Assert
        assert result["message"] is not None
        assert "quest_id" in result
        assert result["individual_quest_count"] == 3
        assert len(result["individual_quest_ids"]) == 3
        
        # Verify weekly quest metadata exists
        # Use get_weekly_quest_by_student_and_period since we don't have last_updated_at
        weekly_quest = self.weekly_quest_dao.get_weekly_quest_by_student_and_period(
            self.test_student_id, 
            self.test_period_id
        )
        assert weekly_quest is not None
        assert weekly_quest.student_id == self.test_student_id
        assert weekly_quest.period_id == self.test_period_id
        
        # Verify individual quests exist
        individual_quests = self.individual_quest_dao.get_quests_by_quest_id_gsi(result["quest_id"])
        assert len(individual_quests) >= 3
        
        # Store for cleanup
        self.test_quest_id = result["quest_id"]
        self.test_individual_quest_ids.extend(result["individual_quest_ids"])
    
    def test_update_weekly_quest_with_homework(self):
        """Test updating individual quests with homework data."""
        # Arrange - create weekly quest and individual quests
        schedule_data = {
            "list_of_quests": [
                {"Name": "Quest 1", "Skills": "Python", "Week": 1},
                {"Name": "Quest 2", "Skills": "JavaScript", "Week": 2}
            ]
        }
        schedule_result = self.service.save_schedule_to_weekly_quests(
            schedule_data,
            self.test_student_id,
            self.test_period_id
        )
        self.test_quest_id = schedule_result["quest_id"]
        self.test_individual_quest_ids.extend(schedule_result["individual_quest_ids"])
        
        homework_data = {
            "list_of_quests": [
                {
                    "Name": "Updated Quest 1",
                    "Week": 1,
                    "instructions": "Complete this quest",
                    "rubric": {"criteria": "test"}
                },
                {
                    "Name": "Updated Quest 2",
                    "Week": 2,
                    "instructions": "Complete this quest too",
                    "rubric": {"criteria": "test2"}
                }
            ]
        }
        
        # Act
        result = self.service.update_weekly_quest_with_homework(
            homework_data,
            self.test_student_id,
            self.test_period_id
        )
        
        # Assert
        assert result["updated_quests_count"] >= 2
        
        # Verify individual quests were updated
        individual_quests = self.individual_quest_dao.get_quests_by_quest_id_gsi(self.test_quest_id)
        quest_by_week = {q["week"]: q for q in individual_quests}
        
        assert quest_by_week[1]["instructions"] == "Complete this quest"
        assert quest_by_week[2]["instructions"] == "Complete this quest too"
    
    def test_get_weekly_quests_for_student(self):
        """Test getting weekly quests with individual quests populated."""
        # Arrange
        schedule_data = {
            "list_of_quests": [
                {"Name": "Quest 1", "Skills": "Python", "Week": 1},
                {"Name": "Quest 2", "Skills": "JavaScript", "Week": 2}
            ]
        }
        schedule_result = self.service.save_schedule_to_weekly_quests(
            schedule_data,
            self.test_student_id,
            self.test_period_id
        )
        self.test_quest_id = schedule_result["quest_id"]
        self.test_individual_quest_ids.extend(schedule_result["individual_quest_ids"])
        
        # Act
        result = self.service.get_weekly_quests_for_student(
            self.test_student_id,
            self.test_period_id
        )
        
        # Assert
        assert result is not None
        assert result["quest_id"] == self.test_quest_id
        assert "quests" in result
        assert len(result["quests"]) >= 2
        assert all("individual_quest_id" in q for q in result["quests"])
        assert all("week" in q for q in result["quests"])
    
    def test_get_individual_quests_for_student(self):
        """Test getting all individual quests for a student."""
        # Arrange
        schedule_data = {
            "list_of_quests": [
                {"Name": "Quest 1", "Skills": "Python", "Week": 1}
            ]
        }
        schedule_result = self.service.save_schedule_to_weekly_quests(
            schedule_data,
            self.test_student_id,
            self.test_period_id
        )
        self.test_quest_id = schedule_result["quest_id"]
        self.test_individual_quest_ids.extend(schedule_result["individual_quest_ids"])
        
        # Act
        results = self.service.get_individual_quests_for_student(self.test_student_id)
        
        # Assert
        assert isinstance(results, list)
        assert len(results) >= 1
        assert any(r["student_id"] == self.test_student_id for r in results)
    
    def test_get_individual_quests_for_student_and_period(self):
        """Test getting individual quests for a student and period."""
        # Arrange
        schedule_data = {
            "list_of_quests": [
                {"Name": "Quest 1", "Skills": "Python", "Week": 1}
            ]
        }
        schedule_result = self.service.save_schedule_to_weekly_quests(
            schedule_data,
            self.test_student_id,
            self.test_period_id
        )
        self.test_quest_id = schedule_result["quest_id"]
        self.test_individual_quest_ids.extend(schedule_result["individual_quest_ids"])
        
        # Act
        results = self.service.get_individual_quests_for_student_and_period(
            self.test_student_id,
            self.test_period_id
        )
        
        # Assert
        assert isinstance(results, list)
        assert len(results) >= 1
        assert all(r["student_id"] == self.test_student_id and 
                  r["period_id"] == self.test_period_id for r in results)
    
    def test_update_individual_quest_status(self):
        """Test updating individual quest status."""
        # Arrange
        schedule_data = {
            "list_of_quests": [
                {"Name": "Quest 1", "Skills": "Python", "Week": 1}
            ]
        }
        schedule_result = self.service.save_schedule_to_weekly_quests(
            schedule_data,
            self.test_student_id,
            self.test_period_id
        )
        self.test_quest_id = schedule_result["quest_id"]
        individual_quest_id = schedule_result["individual_quest_ids"][0]
        self.test_individual_quest_ids.append(individual_quest_id)
        
        # Act
        result = self.service.update_individual_quest_status(
            self.test_quest_id,
            individual_quest_id,
            "in_progress"
        )
        
        # Assert
        assert result["status"] == "in_progress"
        
        # Verify status was updated in database
        quest = self.individual_quest_dao.get_individual_quest_by_id(individual_quest_id)
        assert quest["status"] == "in_progress"
    
    def test_get_individual_quest_by_id(self):
        """Test getting an individual quest by ID."""
        # Arrange
        schedule_data = {
            "list_of_quests": [
                {"Name": "Quest 1", "Skills": "Python", "Week": 1}
            ]
        }
        schedule_result = self.service.save_schedule_to_weekly_quests(
            schedule_data,
            self.test_student_id,
            self.test_period_id
        )
        self.test_quest_id = schedule_result["quest_id"]
        individual_quest_id = schedule_result["individual_quest_ids"][0]
        self.test_individual_quest_ids.append(individual_quest_id)
        
        # Act
        result = self.service.get_individual_quest_by_id(
            self.test_quest_id,
            individual_quest_id
        )
        
        # Assert
        assert result is not None
        assert result["individual_quest_id"] == individual_quest_id
        assert result["quest_id"] == self.test_quest_id
    
    def test_get_individual_quest_by_id_wrong_quest_id(self):
        """Test getting an individual quest with wrong quest_id returns None."""
        # Arrange
        schedule_data = {
            "list_of_quests": [
                {"Name": "Quest 1", "Skills": "Python", "Week": 1}
            ]
        }
        schedule_result = self.service.save_schedule_to_weekly_quests(
            schedule_data,
            self.test_student_id,
            self.test_period_id
        )
        self.test_quest_id = schedule_result["quest_id"]
        individual_quest_id = schedule_result["individual_quest_ids"][0]
        self.test_individual_quest_ids.append(individual_quest_id)
        
        # Act
        result = self.service.get_individual_quest_by_id(
            "wrong_quest_id",
            individual_quest_id
        )
        
        # Assert
        assert result is None
    
    def test_verify_quest_structure(self):
        """Test verifying quest structure."""
        # Arrange
        schedule_data = {
            "list_of_quests": [
                {"Name": "Quest 1", "Skills": "Python", "Week": 1},
                {"Name": "Quest 2", "Skills": "JavaScript", "Week": 2}
            ]
        }
        schedule_result = self.service.save_schedule_to_weekly_quests(
            schedule_data,
            self.test_student_id,
            self.test_period_id
        )
        self.test_quest_id = schedule_result["quest_id"]
        self.test_individual_quest_ids.extend(schedule_result["individual_quest_ids"])
        
        # Act
        verification = self.service.verify_quest_structure(
            self.test_student_id,
            self.test_period_id
        )
        
        # Assert
        assert "weekly_quest" in verification
        assert "individual_quests" in verification
        assert "verification" in verification
        assert verification["verification"]["all_share_same_quest_id"] is True
        assert verification["verification"]["all_match_student_period"] is True
    
    def test_update_quests_preserving_completed_data(self):
        """Test updating quests while preserving completed quest data."""
        # Arrange - create quests
        schedule_data = {
            "list_of_quests": [
                {"Name": "Quest 1", "Skills": "Python", "Week": 1},
                {"Name": "Quest 2", "Skills": "JavaScript", "Week": 2}
            ]
        }
        schedule_result = self.service.save_schedule_to_weekly_quests(
            schedule_data,
            self.test_student_id,
            self.test_period_id
        )
        self.test_quest_id = schedule_result["quest_id"]
        individual_quest_id_1 = schedule_result["individual_quest_ids"][0]
        individual_quest_id_2 = schedule_result["individual_quest_ids"][1]
        self.test_individual_quest_ids.extend(schedule_result["individual_quest_ids"])
        
        # Mark first quest as completed with grade
        self.individual_quest_dao.update_quest_grade_and_feedback(
            individual_quest_id_1,
            '{"overall_score": "A"}',
            "Great work!"
        )
        
        # New schedule and homework data
        new_schedule_data = {
            "list_of_quests": [
                {"Name": "Updated Quest 1", "Skills": "Python Advanced", "Week": 1},
                {"Name": "Updated Quest 2", "Skills": "JavaScript Advanced", "Week": 2}
            ]
        }
        
        new_homework_data = {
            "list_of_quests": [
                {
                    "Name": "Updated Quest 1",
                    "Week": 1,
                    "instructions": "New instructions",
                    "rubric": {"new": "criteria"}
                },
                {
                    "Name": "Updated Quest 2",
                    "Week": 2,
                    "instructions": "New instructions 2",
                    "rubric": {"new": "criteria2"}
                }
            ]
        }
        
        # Act
        result = self.service.update_quests_preserving_completed_data(
            new_schedule_data,
            new_homework_data,
            self.test_student_id,
            self.test_period_id
        )
        
        # Assert
        assert result["preserved_quests"] >= 1
        assert result["updated_quests"] >= 1
        
        # Verify completed quest was preserved
        quest_1 = self.individual_quest_dao.get_individual_quest_by_id(individual_quest_id_1)
        assert quest_1["grade"] is not None  # Grade should be preserved
        assert quest_1["status"] == "completed"  # Status should be preserved
        
        # Verify incomplete quest was updated
        quest_2 = self.individual_quest_dao.get_individual_quest_by_id(individual_quest_id_2)
        assert quest_2["instructions"] == "New instructions 2"
    
    def test_create_individual_quests_from_homework(self):
        """Test creating individual quests from homework data."""
        # Arrange - create weekly quest metadata first
        weekly_quest = WeeklyQuest(
            quest_id=self.test_quest_id,
            student_id=self.test_student_id,
            period_id=self.test_period_id,
            student_period_key=f"{self.test_student_id}#{self.test_period_id}"
        )
        self.weekly_quest_dao.add_weekly_quest(weekly_quest)
        
        homework_data = {
            "list_of_quests": [
                {
                    "Name": "Quest 1",
                    "Skills": "Python",
                    "Week": 1,
                    "instructions": "Complete this",
                    "rubric": {"criteria": "test"}
                }
            ]
        }
        
        # Act
        result = self.service.create_individual_quests_from_homework(
            homework_data,
            self.test_student_id,
            self.test_period_id
        )
        
        # Assert
        assert result["created_quests_count"] == 1
        assert result["quest_id"] == self.test_quest_id
        
        # Verify individual quest was created
        individual_quests = self.individual_quest_dao.get_quests_by_quest_id_gsi(self.test_quest_id)
        assert len(individual_quests) >= 1
        self.test_individual_quest_ids.extend([q["individual_quest_id"] for q in individual_quests])
    
    def test_parse_grade_data(self):
        """Test parsing grade data."""
        # Test new JSON format
        grade_json = '{"detailed_grade": {"criteria1": "A"}, "overall_score": "A"}'
        result = QuestService.parse_grade_data(grade_json)
        assert result["detailed_grade"] is not None
        assert result["overall_score"] == "A"
        assert result["display_grade"] == "A"
        
        # Test legacy format
        legacy_grade = "B+"
        result = QuestService.parse_grade_data(legacy_grade)
        assert result["overall_score"] == "B+"
        assert result["display_grade"] == "B+"
        
        # Test None
        result = QuestService.parse_grade_data(None)
        assert result["display_grade"] == "Not graded"
    
    def test_format_grade_for_display(self):
        """Test formatting grade for display."""
        # Test new format
        grade_json = '{"overall_score": "A"}'
        result = QuestService.format_grade_for_display(grade_json)
        assert result == "A"
        
        # Test legacy format
        result = QuestService.format_grade_for_display("B+")
        assert result == "B+"
        
        # Test None
        result = QuestService.format_grade_for_display(None)
        assert result == "Not graded"

