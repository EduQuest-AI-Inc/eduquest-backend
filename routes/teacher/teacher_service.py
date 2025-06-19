from data_access.period_dao import PeriodDAO
from models.period import Period
import os
from openai import OpenAI

class TeacherService:
    def __init__(self):
        self.period_dao = PeriodDAO()

    def create_period(self, period_id, course, teacher_id, vector_store_id):
        existing = self.period_dao.get_period_by_id(period_id)
        if existing:
            raise ValueError("Period ID already exists")
        
        initial_id = "asst_bmsuvfNCaHJYmqTlnT52AzXE"  # default; we'll keep reusing this
        update_id = "placeholder_update_assistant_id"  # will be replaced with custom assistant
        ltg_id = "placeholder_ltg_assistant_id"  # will be replaced with custom assistant

        new_period = Period(
            period_id=period_id,
            course=course,
            initial_conversation_assistant_id=initial_id,
            update_assistant_id=update_id,
            vector_store_id=vector_store_id,
            ltg_assistant_id=ltg_id,
            teacher_id=teacher_id
        )

        self.period_dao.add_period(new_period)
        return new_period.to_item()

    def get_periods_by_teacher(self, teacher_id):
        periods = self.period_dao.get_periods_by_teacher_id(teacher_id)
        return [
            {
                "period_id": p.period_id,
                "course": p.course
            }
            for p in periods
        ]
    
    def get_vector_store_id_for_period(self, period_id):
        period = self.period_dao.get_period_by_id(period_id)
        if not period:
            raise ValueError("Period not found")
        return period['vector_store_id']
    
    def create_update_and_ltg_assistants(self, vector_store_id):
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        update_prompt = """You are the Update Assistant for EduQuest, an AI-powered educational platform. You support both students and teachers.
    Your job depends on who you're talking to:
    - If the user is a **teacher**:
    1. Ask the teacher "What have you noticed about [name of student]?" Try to keep your response short (2-3 sentences)
    2. Ask the teacher what changes they would like to make to the student's user or future quests. Try to keep your response short (1-2 sentences)
    3. Update the student user if relevant (e.g., their strengths, weaknesses, interests, or learning style).
    4. Update their Weekly Quests Table if needed (e.g., re-sequencing, modifying difficulty, skipping ahead, etc.).
    5. Return the updated student user and Weekly Quests Table.
    - If the user is a **student**, they will submit their weekly quest. You will:
    1. Grade their submission based on their student user and the provided weekly quest.
    2. Provide constructive feedback.
    3. Update the student user if relevant (e.g., their strengths, weaknesses, interests, or learning style).
    4. Update their Weekly Quests Table if needed (e.g., re-sequencing, modifying difficulty, skipping ahead, etc.).
    5. Return the updated student user and Weekly Quests Table.
    
    At the start of every session, you will receive:
    - The **user role** (`teacher` or `student`).
    - The **student user**.
    - The **weekly quests table**.
    - If the user is a student, you will also receive the **submission** and **week number**.
    Always reflect a warm, encouraging tone with students, and a collaborative tone with teachers. Ask clarifying questions if anything is unclear.
    At the end, you will output a table with the same format you received. """

        ltg_prompt = """You will suggest three long-term goals for a student to work on based on the class they are taking and their strengths, weaknesses, interests, and learning style. This long-term goal should help the student to practice the materials learned in class in the field of their interest in a way that suits their learning style. The student should be able to achieve this long-term goal in 18 weeks while incorporating the things they are learning in the class
    Note: Most important thing is to incorporate the ALL class materials in the JSON course schedule from the file search in the suggested long-term goal. 
    You will only return the three long-term goal suggestions"""

        update_assistant = client.beta.assistants.create(
            name="Update Assistant",
            instructions=update_prompt,
            model="o3-mini",  
            tools=[{"type": "file_search"}],
            tool_resources={"file_search": {"vector_store_ids": [vector_store_id]}}
        )

        ltg_assistant = client.beta.assistants.create(
            name="Long-Term Goal Assistant",
            instructions=ltg_prompt,
            model="gpt-4.1-mini",
            tools=[{"type": "file_search"}],
            tool_resources={"file_search": {"vector_store_ids": [vector_store_id]}}
        )

        return update_assistant.id, ltg_assistant.id

    def update_period_assistants(self, period_id, update_assistant_id, ltg_assistant_id):
        """Update the period with the newly created assistant IDs"""
        updates = {
            "update_assistant_id": update_assistant_id,
            "ltg_assistant_id": ltg_assistant_id
        }
        self.period_dao.update_period(period_id, updates)

