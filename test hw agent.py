from EQ_agents.agent import *
from models.period import Period
from models.student import Student
import asyncio
from agents import Agent, Runner, guardrail_span, trace
import os
from dotenv import load_dotenv
import openai
from openai import OpenAI
import json

load_dotenv()

openai.api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Create student user
golden = Student(
    student_id='golden',
    first_name='golden',
    last_name='huang',
    enrollments = ['123'],
    grade=10)

pre_calc = Period(
    period_id="period_1",
    initial_conversation_assistant_id="assistant_1",
    update_assistant_id="assistant_2",
    ltg_assistant_id="assistant_3",
    teacher_id="teacher_1",
    vector_store_id="vs_682cfbf6f3a88191bfde8d520e939fd6",
    course="course_1")

def process_schedule_by_week(schedule_data: dict):
    """
    Process the schedule data week by week.
    
    Args:
        schedule_data (dict): The schedule data from output.json
    """
    # Create output directory if it doesn't exist
    os.makedirs('homework_outputs', exist_ok=True)
    
    # Get the list of quests
    quests = schedule_data.get('list_of_quests', [])
    
    # Sort quests by week number
    quests.sort(key=lambda x: x['Week'])
    
    # Process each quest
    for quest in quests:
        week_number = quest['Week']
        print(f"\nProcessing Week {week_number}")
        print(f"Quest Description: {quest['Description']}")
        print(f"Skills: {quest['Skills']}")
        
        # Create a single quest schedule
        single_quest = IndividualQuest(
            Description=quest['Description'],
            Skills=quest['Skills'],
            Week=quest['Week']
        )
        
        # Create schedule with single quest
        single_schedule = schedule(list_of_quests=[single_quest])
        
        # Create homework agent for this quest
        hw_agent = HWAgent(golden, pre_calc, single_schedule)
        
        try:
            # Generate homework
            homework = hw_agent.run()
            
            # Save to week-specific file
            output_file = f'homework_outputs/week_{week_number}_homework.json'
            with open(output_file, 'w') as f:
                if isinstance(homework, HomeworkSchedule):
                    json.dump(homework.model_dump(), f, indent=2)
                else:
                    json.dump(homework, f, indent=2)
            print(f"Saved homework for Week {week_number} to {output_file}")
            
        except Exception as e:
            print(f"Error processing Week {week_number}: {str(e)}")
            continue

# Read and process the schedule
with open('output.json', 'r') as f:
    schedule_data = json.load(f)
    print("Processing schedule...")
    process_schedule_by_week(schedule_data)

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