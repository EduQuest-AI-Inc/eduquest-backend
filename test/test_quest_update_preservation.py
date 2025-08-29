import sys
import os
import json
from datetime import datetime, timezone

# Add the parent directory to Python path so we can import from eduquest-backend
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data_access.period_dao import PeriodDAO
from data_access.student_dao import StudentDAO
from data_access.individual_quest_dao import IndividualQuestDAO
from routes.quest.quest_service import QuestService
from routes.period.period_service import PeriodService
from models.individual_quest import IndividualQuest
from decimal import Decimal
import uuid

def setup_test_data():
    """Create test data: student with completed quests and upcoming quests"""
    print("=== Setting Up Test Data ===")
    
    # DAOs
    student_dao = StudentDAO()
    period_dao = PeriodDAO()
    quest_dao = IndividualQuestDAO()
    quest_service = QuestService()
    
    # Use existing test student and period
    test_student_id = "Golden"  # Use existing test student
    test_period_id = "PRECALC-58F9-88F5"  # Use existing test period
    
    # Get test student
    student = student_dao.get_student_by_id(test_student_id)
    if not student:
        print(f"Test student {test_student_id} not found - skipping test")
        return None, None
    
    # Get test period  
    period = period_dao.get_period_by_id(test_period_id)
    if not period:
        print(f"Test period {test_period_id} not found - skipping test")
        return None, None
    
    print(f"Using student: {test_student_id}")
    print(f"Using period: {test_period_id}")
    
    # Get existing quests for this student/period
    existing_quests = quest_service.get_individual_quests_for_student_and_period(test_student_id, test_period_id)
    
    # If there are existing quests, we'll use them for the test
    if existing_quests:
        print(f"Found {len(existing_quests)} existing quests to test with")
        
        # Add some test grades to a few quests to simulate completed work
        graded_count = 0
        for quest in existing_quests[:3]:  # Grade first 3 quests
            if not quest.get('grade'):  # Only grade if not already graded
                quest_dao.update_quest_grade_and_feedback(
                    quest['individual_quest_id'],
                    "88",
                    f"Test feedback for week {quest['week']} - good work!"
                )
                graded_count += 1
                print(f"Added test grade to week {quest['week']} quest")
        
        if graded_count > 0:
            print(f"Added test grades to {graded_count} quests for testing")
        
        return test_student_id, test_period_id
    else:
        print("No existing quests found - this test needs existing quest data")
        return None, None

def capture_quest_state(student_id, period_id):
    """Capture the current state of all quests for comparison"""
    quest_service = QuestService()
    quests = quest_service.get_individual_quests_for_student_and_period(student_id, period_id)
    
    quest_state = {}
    for quest in quests:
        quest_state[quest['week']] = {
            'individual_quest_id': quest['individual_quest_id'],
            'description': quest.get('description', ''),
            'grade': quest.get('grade'),
            'feedback': quest.get('feedback'),
            'status': quest.get('status', 'not_started'),
            'instructions': quest.get('instructions', ''),
            'rubric': quest.get('rubric', {}),
            'last_updated_at': quest.get('last_updated_at')
        }
    
    return quest_state

def simulate_quest_update_with_change(student_id, period_id):
    """Simulate the quest update process when change=True"""
    print("\n=== Simulating Quest Update Process ===")
    
    # For this test, we'll call the period service method directly
    # In the real system, this would be called from conversation_service
    
    # Mock recommended change
    recommended_change = "Increase difficulty for future math problems to challenge the student more, focus on advanced algebra concepts"
    
    period_service = PeriodService()
    
    try:
        # We need to simulate an auth token - let's create a mock session for testing
        from data_access.session_dao import SessionDAO
        session_dao = SessionDAO()
        
        # Check if there's an existing session for this student
        # In a real test environment, we'd create a proper test session
        # For now, we'll bypass the auth check by calling the core logic directly
        
        print("DEBUG: Bypassing auth for test - calling quest update logic directly")
        
        # Get required objects
        student = period_service.student_dao.get_student_by_id(student_id)
        period = period_service.period_dao.get_period_by_id(period_id)
        
        if not student or not period:
            raise Exception("Student or period not found")
        
        # Import the agent classes
        from EQ_agents.agent import SchedulesAgent, HWAgent
        
        # Step 1: Generate new schedule with recommended changes
        print("DEBUG: Generating new schedule with recommended changes...")
        schedules_agent = SchedulesAgent(student, period, recommended_change)
        schedule = schedules_agent.run()
        schedule_dict = schedule.model_dump()
        print(f"DEBUG: New schedule generated with {len(schedule_dict.get('list_of_quests', []))} quests")
        
        # Step 2: Generate new homework based on the new schedule  
        print("DEBUG: Generating new homework based on new schedule...")
        
        # Convert schedule to format needed by homework agent
        schedule_quests = []
        for quest_data in schedule_dict.get("list_of_quests", []):
            schedule_quests.append({
                "Name": quest_data.get("Name", ""),
                "Skills": quest_data.get("Skills", ""),
                "Week": quest_data.get("Week", 1)
            })
        
        # Generate homework with the new schedule
        homework_agent = HWAgent(student, period, schedule_quests)
        homework = homework_agent.run()
        
        # Convert homework to expected dict format
        if isinstance(homework, list):
            homework_dict = {"list_of_quests": []}
            for quest in homework:
                if hasattr(quest, 'model_dump'):
                    homework_dict["list_of_quests"].append(quest.model_dump())
                elif isinstance(quest, dict):
                    homework_dict["list_of_quests"].append(quest)
                else:
                    quest_dict = {
                        "Name": getattr(quest, 'Name', ''),
                        "Skills": getattr(quest, 'Skills', ''),
                        "Week": getattr(quest, 'Week', 1),
                        "instructions": getattr(quest, 'instructions', ''),
                        "rubric": getattr(quest, 'rubric', {})
                    }
                    homework_dict["list_of_quests"].append(quest_dict)
        else:
            homework_dict = homework if isinstance(homework, dict) else homework.model_dump()
        
        print(f"DEBUG: New homework generated with {len(homework_dict.get('list_of_quests', []))} quests")
        
        # Step 3: Safely update quests preserving completed data
        print("DEBUG: Safely updating quests while preserving completed data...")
        update_result = period_service.quest_service.update_quests_preserving_completed_data(
            schedule_dict, 
            homework_dict, 
            student_id, 
            period_id
        )
        print(f"DEBUG: Safe quest update completed: {update_result.get('message', 'No message')}")
        
        return {
            "success": True,
            "message": "Quests updated successfully based on recommended changes while preserving completed work",
            "recommended_change": recommended_change,
            "quest_update_details": update_result,
            "preserved_quests": update_result.get("preserved_quests", 0),
            "updated_quests": update_result.get("updated_quests", 0),
            "created_quests": update_result.get("created_quests", 0),
            "total_quests": update_result.get("total_quests", 0)
        }
        
    except Exception as e:
        print(f"Error during quest update: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}

def compare_quest_states(before_state, after_state):
    """Compare quest states to verify preservation of past quest data"""
    print("\n=== Comparing Quest States ===")
    
    issues_found = []
    
    for week in sorted(before_state.keys()):
        before_quest = before_state[week]
        after_quest = after_state.get(week)
        
        if not after_quest:
            issues_found.append(f"Week {week}: Quest disappeared after update!")
            continue
        
        print(f"\nWeek {week}:")
        print(f"  Quest ID: {before_quest['individual_quest_id']} -> {after_quest['individual_quest_id']}")
        
        # Check if critical data was preserved for completed/graded quests
        if before_quest['grade'] is not None:
            if before_quest['grade'] != after_quest['grade']:
                issues_found.append(f"Week {week}: Grade changed from {before_quest['grade']} to {after_quest['grade']}")
            else:
                print(f"  ✓ Grade preserved: {before_quest['grade']}")
        
        if before_quest['feedback'] is not None:
            if before_quest['feedback'] != after_quest['feedback']:
                issues_found.append(f"Week {week}: Feedback changed from '{before_quest['feedback']}' to '{after_quest['feedback']}'")
            else:
                print(f"  ✓ Feedback preserved: {before_quest['feedback']}")
        
        if before_quest['status'] in ['completed', 'in_progress']:
            if before_quest['status'] != after_quest['status']:
                issues_found.append(f"Week {week}: Status changed from {before_quest['status']} to {after_quest['status']}")
            else:
                print(f"  ✓ Status preserved: {before_quest['status']}")
        
        # Check if quest content was updated for future quests
        if before_quest['status'] == 'not_started':
            if before_quest['instructions'] != after_quest['instructions']:
                print(f"  ✓ Instructions updated for future quest")
            if before_quest['rubric'] != after_quest['rubric']:
                print(f"  ✓ Rubric updated for future quest")
    
    return issues_found

def run_preservation_test():
    """Main test function"""
    print("🧪 STARTING QUEST UPDATE PRESERVATION TEST")
    print("=" * 50)
    
    # Setup test data
    student_id, period_id = setup_test_data()
    if not student_id or not period_id:
        print("❌ Test setup failed - missing required test data")
        return False
    
    # Capture initial state
    print("\n📸 Capturing initial quest state...")
    before_state = capture_quest_state(student_id, period_id)
    print(f"Found {len(before_state)} quests to monitor")
    
    for week, quest in sorted(before_state.items()):
        status_icon = "✅" if quest['grade'] else "⏳"
        print(f"  {status_icon} Week {week}: {quest['status']} - Grade: {quest['grade']} - ID: {quest['individual_quest_id'][:8]}")
    
    # Simulate quest update
    print("\n🔄 Simulating quest update with recommended changes...")
    update_result = simulate_quest_update_with_change(student_id, period_id)
    
    if not update_result.get("success"):
        print(f"❌ Quest update simulation failed: {update_result.get('error', 'Unknown error')}")
        return False
    
    # Show update results
    details = update_result.get("quest_update_details", {})
    print(f"✅ Quest update completed successfully!")
    print(f"  Preserved quests (with grades/completed): {details.get('preserved_quests', 0)}")
    print(f"  Updated quests (future quests): {details.get('updated_quests', 0)}")
    print(f"  Created quests (new weeks): {details.get('created_quests', 0)}")
    print(f"  Total quests: {details.get('total_quests', 0)}")
    
    # Capture state after update
    print("\n📸 Capturing post-update quest state...")
    after_state = capture_quest_state(student_id, period_id)
    print(f"Found {len(after_state)} quests after update")
    
    # Compare states
    issues = compare_quest_states(before_state, after_state)
    
    # Report results
    print("\n" + "=" * 50)
    if issues:
        print("❌ PRESERVATION TEST FAILED")
        print("Issues found:")
        for issue in issues:
            print(f"  • {issue}")
        return False
    else:
        print("✅ PRESERVATION TEST PASSED")
        print("All past quest data (grades, feedback, status) was preserved!")
        print("Future quests were appropriately updated with new content.")
        print(f"\nSummary:")
        print(f"  📊 Total quests tested: {len(before_state)}")
        print(f"  🛡️  Preserved completed work: {details.get('preserved_quests', 0)} quests")
        print(f"  🔄 Updated future quests: {details.get('updated_quests', 0)} quests") 
        print(f"  ➕ Created new quests: {details.get('created_quests', 0)} quests")
        return True

if __name__ == "__main__":
    success = run_preservation_test()
    sys.exit(0 if success else 1) 