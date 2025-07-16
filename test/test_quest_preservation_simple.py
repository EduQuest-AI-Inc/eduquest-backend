import sys
import os
import json
from datetime import datetime, timezone

# Add the parent directory to Python path so we can import from eduquest-backend
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data_access.individual_quest_dao import IndividualQuestDAO
from routes.quest.quest_service import QuestService
from models.individual_quest import IndividualQuest
import uuid

def create_test_quest(student_id, period_id, week, quest_id, has_grade=False, status="not_started"):
    """Create a test quest for testing preservation logic"""
    individual_quest_id = str(uuid.uuid4())
    
    quest = IndividualQuest(
        individual_quest_id=individual_quest_id,
        quest_id=quest_id,
        student_id=student_id,
        period_id=period_id,
        description=f"Original Test Quest Week {week}",
        grade="85" if has_grade else None,
        feedback=f"Original feedback for week {week}" if has_grade else None,
        skills=f"Original math skills week {week}",
        week=week,
        instructions=f"Original instructions for week {week}",
        rubric={"criteria": f"Original week {week} rubric", "points": 100},
        status=status
    )
    return quest

def test_quest_preservation_logic():
    """Test the quest preservation logic without running full agents"""
    print("🧪 TESTING QUEST PRESERVATION LOGIC")
    print("=" * 50)
    
    # Test IDs
    test_student_id = "test_preservation_student"
    test_period_id = "test_preservation_period"
    test_quest_id = str(uuid.uuid4())
    
    quest_dao = IndividualQuestDAO()
    quest_service = QuestService()
    
    try:
        # Step 1: Create test quests with different states
        print("📝 Creating test quests...")
        
        test_quests = [
            create_test_quest(test_student_id, test_period_id, 1, test_quest_id, has_grade=True, status="completed"),
            create_test_quest(test_student_id, test_period_id, 2, test_quest_id, has_grade=True, status="completed"),
            create_test_quest(test_student_id, test_period_id, 3, test_quest_id, has_grade=False, status="in_progress"),
            create_test_quest(test_student_id, test_period_id, 4, test_quest_id, has_grade=False, status="not_started"),
            create_test_quest(test_student_id, test_period_id, 5, test_quest_id, has_grade=False, status="not_started"),
        ]
        
        # Add quests to database
        for quest in test_quests:
            quest_dao.add_individual_quest(quest)
            status_icon = "✅" if quest.grade else "⏳"
            print(f"  {status_icon} Week {quest.week}: {quest.status} - Grade: {quest.grade}")
        
        # Step 2: Capture initial state
        print("\n📸 Capturing initial state...")
        initial_quests = quest_service.get_individual_quests_for_student_and_period(test_student_id, test_period_id)
        initial_by_week = {quest['week']: quest for quest in initial_quests}
        
        # Step 3: Create mock new schedule/homework data that would change quest content
        print("\n🔄 Creating mock updated quest data...")
        
        mock_schedule_data = {
            "list_of_quests": [
                {"Name": "NEW Quest Week 1", "Skills": "NEW math skills week 1", "Week": 1},
                {"Name": "NEW Quest Week 2", "Skills": "NEW math skills week 2", "Week": 2},
                {"Name": "NEW Quest Week 3", "Skills": "NEW math skills week 3", "Week": 3},
                {"Name": "NEW Quest Week 4", "Skills": "NEW math skills week 4", "Week": 4},
                {"Name": "NEW Quest Week 5", "Skills": "NEW math skills week 5", "Week": 5},
                {"Name": "NEW Quest Week 6", "Skills": "NEW math skills week 6", "Week": 6},  # New week
            ]
        }
        
        mock_homework_data = {
            "list_of_quests": [
                {"Name": "NEW Quest Week 1", "Skills": "NEW math skills week 1", "Week": 1, 
                 "instructions": "NEW instructions week 1", "rubric": {"criteria": "NEW rubric 1"}},
                {"Name": "NEW Quest Week 2", "Skills": "NEW math skills week 2", "Week": 2,
                 "instructions": "NEW instructions week 2", "rubric": {"criteria": "NEW rubric 2"}},
                {"Name": "NEW Quest Week 3", "Skills": "NEW math skills week 3", "Week": 3,
                 "instructions": "NEW instructions week 3", "rubric": {"criteria": "NEW rubric 3"}},
                {"Name": "NEW Quest Week 4", "Skills": "NEW math skills week 4", "Week": 4,
                 "instructions": "NEW instructions week 4", "rubric": {"criteria": "NEW rubric 4"}},
                {"Name": "NEW Quest Week 5", "Skills": "NEW math skills week 5", "Week": 5,
                 "instructions": "NEW instructions week 5", "rubric": {"criteria": "NEW rubric 5"}},
                {"Name": "NEW Quest Week 6", "Skills": "NEW math skills week 6", "Week": 6,
                 "instructions": "NEW instructions week 6", "rubric": {"criteria": "NEW rubric 6"}},
            ]
        }
        
        # Step 4: Apply the safe update method
        print("\n🛡️ Applying safe quest update...")
        result = quest_service.update_quests_preserving_completed_data(
            mock_schedule_data, 
            mock_homework_data, 
            test_student_id, 
            test_period_id
        )
        
        print(f"Update result: {result['message']}")
        print(f"  Preserved: {result['preserved_quests']}")
        print(f"  Updated: {result['updated_quests']}")
        print(f"  Created: {result['created_quests']}")
        
        # Step 5: Verify preservation
        print("\n🔍 Verifying preservation...")
        updated_quests = quest_service.get_individual_quests_for_student_and_period(test_student_id, test_period_id)
        updated_by_week = {quest['week']: quest for quest in updated_quests}
        
        issues = []
        
        for week in range(1, 7):
            initial_quest = initial_by_week.get(week)
            updated_quest = updated_by_week.get(week)
            
            print(f"\nWeek {week}:")
            
            if week <= 5 and initial_quest:  # Existing quests
                if not updated_quest:
                    issues.append(f"Week {week}: Quest disappeared!")
                    continue
                
                # Check preservation based on completion status
                if initial_quest.get('grade'):
                    # Graded quest - should preserve grade, feedback, description, instructions, rubric
                    if initial_quest['grade'] != updated_quest.get('grade'):
                        issues.append(f"Week {week}: Grade changed from {initial_quest['grade']} to {updated_quest.get('grade')}")
                    else:
                        print(f"  ✅ Grade preserved: {initial_quest['grade']}")
                    
                    if initial_quest['feedback'] != updated_quest.get('feedback'):
                        issues.append(f"Week {week}: Feedback changed")
                    else:
                        print(f"  ✅ Feedback preserved")
                    
                    # For completed quests, instructions/rubric should NOT change
                    if initial_quest['instructions'] != updated_quest.get('instructions'):
                        issues.append(f"Week {week}: Instructions changed for completed quest")
                    else:
                        print(f"  ✅ Instructions preserved for completed quest")
                        
                elif initial_quest.get('status') in ['completed', 'in_progress']:
                    # In-progress/completed but not graded - should preserve status
                    if initial_quest['status'] != updated_quest.get('status'):
                        issues.append(f"Week {week}: Status changed from {initial_quest['status']} to {updated_quest.get('status')}")
                    else:
                        print(f"  ✅ Status preserved: {initial_quest['status']}")
                        
                else:
                    # Not started quest - should be updated with new content
                    if updated_quest.get('instructions') == initial_quest.get('instructions'):
                        print(f"  ⚠️  Instructions not updated for not-started quest")
                    else:
                        print(f"  ✅ Instructions updated for future quest")
                        
            elif week == 6:  # New quest
                if updated_quest:
                    print(f"  ✅ New quest created for week {week}")
                else:
                    issues.append(f"Week {week}: New quest not created")
        
        # Step 6: Report results
        print("\n" + "=" * 50)
        if issues:
            print("❌ PRESERVATION TEST FAILED")
            print("Issues found:")
            for issue in issues:
                print(f"  • {issue}")
            return False
        else:
            print("✅ PRESERVATION TEST PASSED")
            print("Quest preservation logic works correctly!")
            return True
            
    except Exception as e:
        print(f"❌ Test failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # Cleanup: Remove test quests
        print("\n🧹 Cleaning up test data...")
        try:
            test_quests = quest_service.get_individual_quests_for_student_and_period(test_student_id, test_period_id)
            for quest in test_quests:
                quest_dao.delete_individual_quest(quest['individual_quest_id'])
            print(f"Cleaned up {len(test_quests)} test quests")
        except Exception as cleanup_error:
            print(f"Cleanup error: {cleanup_error}")

if __name__ == "__main__":
    success = test_quest_preservation_logic()
    sys.exit(0 if success else 1) 