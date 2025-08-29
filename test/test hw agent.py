import sys
import os

# Add the parent directory to Python path so we can import from eduquest-backend
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from typing import Dict, Any
from data_access.period_dao import PeriodDAO
from data_access.session_dao import SessionDAO
from data_access.student_dao import StudentDAO
from data_access.conversation_dao import ConversationDAO
from data_access.enrollment_dao import EnrollmentDAO
from models.conversation import Conversation
from models.enrollment import Enrollment
from models.session import Session
from assistants import ltg
from datetime import datetime, timezone
from EQ_agents.agent import SchedulesAgent, HWAgent
from routes.quest.quest_service import QuestService
import json
from dotenv import load_dotenv
from openai import OpenAI
from models.student import Student
from models.period import Period
# from models.homework import HomeworkSchedule
import openai
from flask_jwt_extended import create_access_token
from flask import Flask

load_dotenv()

# Initialize Flask app for JWT token creation (if needed)
app = Flask(__name__)
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'fallback-secret')

openai.api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

period_dao = PeriodDAO()
session_dao = SessionDAO()
student_dao = StudentDAO()
conversation_dao = ConversationDAO()
enrollment_dao = EnrollmentDAO()
quest_service = QuestService()

# Example usage:
# auth_token = create_test_session()  # Creates real session in DB
# auth_token = create_test_jwt_token()  # Creates JWT token only
# auth_token = test_auth_token  # Uses simple string for basic testing

# For this test, let's just comment out the session check since we don't need it
# session_dao.get_sessions_by_auth_token(auth_token)  # Commented out - auth_token not defined
student = student_dao.get_student_by_id("Golden")
weekly_schedule = quest_service.get_weekly_quests_for_student('Golden', 'PRECALC-58F9-88F5')
period = period_dao.get_period_by_id('PRECALC-58F9-88F5')

# Test the homework agent
print("\n=== Testing HW Agent ===")
homework_agent = HWAgent(
                student, 
                period, 
                weekly_schedule.quests)

homework = homework_agent.run()
print(homework[0].rubric)
# print(type(weekly_schedule.quests[0].skills))
# def process_schedule_by_week(schedule_data: dict):
#     """
#     Process the schedule data week by week.
    
#     Args:
#         schedule_data (dict): The schedule data from output.json
#     """
#     # Create output directory if it doesn't exist
#     os.makedirs('homework_outputs', exist_ok=True)
    
#     # Get the list of quests
#     quests = schedule_data.get('list_of_quests', [])
    
#     # Sort quests by week number
#     quests.sort(key=lambda x: x['Week'])
    
#     # Process each quest
#     for quest in quests:
#         week_number = quest['Week']
#         print(f"\nProcessing Week {week_number}")
#         print(f"Quest Description: {quest['Description']}")
#         print(f"Skills: {quest['Skills']}")
        
#         # Create a single quest schedule
#         single_quest = IndividualQuest(
#             Description=quest['Description'],
#             Skills=quest['Skills'],
#             Week=quest['Week']
#         )
        
#         # Create schedule with single quest
#         single_schedule = schedule(list_of_quests=[single_quest])
        
#         # Create homework agent for this quest
#         hw_agent = HWAgent(golden, pre_calc, single_schedule)
        
#         try:
#             # Generate homework
#             homework = hw_agent.run()
            
#             # Save to week-specific file
#             output_file = f'homework_outputs/week_{week_number}_homework.json'
#             with open(output_file, 'w') as f:
#                 if isinstance(homework, HomeworkSchedule):
#                     json.dump(homework.model_dump(), f, indent=2)
#                 else:
#                     json.dump(homework, f, indent=2)
#             print(f"Saved homework for Week {week_number} to {output_file}")
            
#         except Exception as e:
#             print(f"Error processing Week {week_number}: {str(e)}")
#             continue

# # Read and process the schedule
# with open('output.json', 'r') as f:
#     schedule_data = json.load(f)
#     print("Processing schedule...")
#     process_schedule_by_week(schedule_data)

# Create homework assignments based on the schedule
# hw_agent = HWAgent(golden, pre_calc, schedule_data[0])

# print(schedule)

# # --- Main Function ---
# def process_week(week_number: int, quest: IndividualQuest) -> dict:
#     """Process a single week's homework assignment"""
#     print(f"\nProcessing Week {week_number}...")
#     print(f"Quest: {quest.Description}")
    
#     # Create a single quest schedule for this week
#     single_quest_schedule = schedule(list_of_quests=[quest])
#     hw_agent.schedule = single_quest_schedule
    
#     # Generate homework for this week
#     homework = hw_agent.run()
    
#     # Convert to dictionary for JSON serialization
#     if isinstance(homework, HomeworkSchedule):
#         return homework.model_dump()
#     return homework

# def main():
#     # Create output directory if it doesn't exist
#     os.makedirs('homework_outputs', exist_ok=True)
    
#     # Process each week
#     for quest in schedule.list_of_quests:
#         week_number = quest.Week
#         output = process_week(week_number, quest)
        
#         # Save to individual week file
#         output_file = f'homework_outputs/week_{week_number}_homework.json'
#         with open(output_file, 'w') as f:
#             json.dump(output, f, indent=2)
#         print(f"Saved homework for Week {week_number} to {output_file}")
    
#     # Also save complete output
#     with open('homework_output.json', 'w') as f:
#         json.dump({
#             "student": golden.model_dump(),
#             "schedule": schedule.model_dump(),
#             "homework_assignments": [process_week(quest.Week, quest) for quest in schedule.list_of_quests]
#         }, f, indent=2)
#     print("\nSaved complete homework schedule to homework_output.json")

# if __name__ == "__main__":
#     main() 