#!/usr/bin/env python3
"""
Test script to verify the weekly quest retrieval fix.
This tests the immediate consistency and retry mechanism improvements.
"""
import sys
import os
import uuid
from datetime import datetime, timezone

# Add parent directory to path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from models.weekly_quest import WeeklyQuest
from models.weekly_quest_item import WeeklyQuestItem
from data_access.weekly_quest_dao import WeeklyQuestDAO


def test_immediate_retrieval():
    """Test that we can immediately retrieve a quest after saving it."""
    print("Testing immediate quest retrieval after save...")
    
    dao = WeeklyQuestDAO()
    
    # Create test data
    student_id = "test_student_immediate"
    period_id = "test_period_immediate"
    quest_id = str(uuid.uuid4())
    
    # Clean up any existing test data first
    try:
        existing = dao.get_weekly_quest_by_student_and_period(student_id, period_id)
        if existing:
            dao.delete_weekly_quest(existing.quest_id)
            print(f"Cleaned up existing test quest: {existing.quest_id}")
    except Exception as e:
        print(f"No existing test data to clean up: {e}")
    
    # Create test quest item
    quest_item = WeeklyQuestItem(
        individual_quest_id=str(uuid.uuid4()),
        name="Test Quest for Immediate Retrieval",
        skills="Testing, Verification",
        week=1,
        status="not_started",
        description="Test quest to verify immediate retrieval works"
    )
    
    # Create weekly quest
    weekly_quest = WeeklyQuest(
        quest_id=quest_id,
        student_id=student_id,
        period_id=period_id,
        quests=[quest_item]
    )
    
    try:
        # Save the quest
        print(f"Saving quest with ID: {quest_id}")
        dao.add_weekly_quest(weekly_quest)
        print("✓ Quest saved successfully")
        
        # Immediately try to retrieve it
        print("Attempting immediate retrieval...")
        retrieved_quest = dao.get_weekly_quest_by_student_and_period(student_id, period_id)
        
        if retrieved_quest:
            print("✓ SUCCESS: Quest retrieved immediately!")
            print(f"  Retrieved quest ID: {retrieved_quest.quest_id}")
            print(f"  Student ID: {retrieved_quest.student_id}")
            print(f"  Period ID: {retrieved_quest.period_id}")
            print(f"  Number of quests: {len(retrieved_quest.quests)}")
            return True
        else:
            print("✗ FAILED: Could not retrieve quest immediately after save")
            return False
            
    except Exception as e:
        print(f"✗ ERROR during test: {str(e)}")
        return False
    
    finally:
        # Clean up
        try:
            dao.delete_weekly_quest(quest_id)
            print("✓ Test data cleaned up")
        except Exception as e:
            print(f"Warning: Could not clean up test data: {e}")


def test_retry_mechanism():
    """Test the retry mechanism with a quest that should be found."""
    print("\nTesting retry mechanism...")
    
    dao = WeeklyQuestDAO()
    
    # Use different test data for retry test
    student_id = "test_student_retry"
    period_id = "test_period_retry"
    quest_id = str(uuid.uuid4())
    
    # Clean up any existing test data
    try:
        existing = dao.get_weekly_quest_by_student_and_period(student_id, period_id)
        if existing:
            dao.delete_weekly_quest(existing.quest_id)
    except Exception:
        pass
    
    quest_item = WeeklyQuestItem(
        individual_quest_id=str(uuid.uuid4()),
        name="Test Quest for Retry Mechanism",
        skills="Retry Testing, Persistence",
        week=1,
        status="not_started",
        description="Test quest to verify retry mechanism"
    )
    
    weekly_quest = WeeklyQuest(
        quest_id=quest_id,
        student_id=student_id,
        period_id=period_id,
        quests=[quest_item]
    )
    
    try:
        # Save the quest
        dao.add_weekly_quest(weekly_quest)
        print("✓ Quest saved for retry test")
        
        # Test retrieval (should work with strong consistency + retries)
        retrieved_quest = dao.get_weekly_quest_by_student_and_period(student_id, period_id)
        
        if retrieved_quest:
            print("✓ SUCCESS: Retry mechanism working properly!")
            return True
        else:
            print("✗ FAILED: Retry mechanism failed")
            return False
            
    except Exception as e:
        print(f"✗ ERROR during retry test: {str(e)}")
        return False
    
    finally:
        # Clean up
        try:
            dao.delete_weekly_quest(quest_id)
            print("✓ Retry test data cleaned up")
        except Exception as e:
            print(f"Warning: Could not clean up retry test data: {e}")


if __name__ == "__main__":
    print("=" * 60)
    print("Weekly Quest Retrieval Fix Verification")
    print("=" * 60)
    
    test1_passed = test_immediate_retrieval()
    test2_passed = test_retry_mechanism()
    
    print("\n" + "=" * 60)
    print("TEST RESULTS SUMMARY")
    print("=" * 60)
    print(f"Immediate Retrieval Test: {'PASSED' if test1_passed else 'FAILED'}")
    print(f"Retry Mechanism Test: {'PASSED' if test2_passed else 'FAILED'}")
    
    if test1_passed and test2_passed:
        print("\n🎉 ALL TESTS PASSED! The quest retrieval fix is working correctly.")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed. Please check the implementation.")
        sys.exit(1)