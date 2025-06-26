from data_access.period_dao import PeriodDAO
from models.period import Period
import os
import assistants
from openai import OpenAI
import uuid
import re

class TeacherService:
    def __init__(self):
        self.period_dao = PeriodDAO()

    def generate_period_id(self, course_name: str) -> str:
        clean_course = re.sub(r'[^a-zA-Z0-9]', '', course_name).upper()
        if len(clean_course) > 8:
            clean_course = clean_course[:8]
        
        random_part1 = str(uuid.uuid4())[:4].upper()
        random_part2 = str(uuid.uuid4())[:4].upper()
        
        period_id = f"{clean_course}-{random_part1}-{random_part2}"
        return period_id

    def create_period(self, course, teacher_id, vector_store_id, file_urls):
        period_id = self.generate_period_id(course)
        
        existing = self.period_dao.get_period_by_id(period_id)
        attempts = 0
        while existing and attempts < 5:
            period_id = self.generate_period_id(course)
            existing = self.period_dao.get_period_by_id(period_id)
            attempts += 1
        
        if existing:
            raise ValueError("Unable to generate unique period ID")
        
        print(f"Creating period with ID: {period_id}")
        
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
            teacher_id=teacher_id,
            file_urls=file_urls
        )
        print(f"Created Period object with file_urls: {new_period.file_urls}")

        self.period_dao.add_period(new_period)
        result = new_period.to_item()
        print(f"Saved period with file_urls: {result.get('file_urls')}")
        return result

    def get_periods_by_teacher(self, teacher_id):
        periods = self.period_dao.get_periods_by_teacher_id(teacher_id)
        return [
            {
                "period_id": p.period_id,
                "course": p.course
            }
            for p in periods
        ]
    
    def get_period_by_id(self, period_id):
        """Get a period by its ID"""
        return self.period_dao.get_period_by_id(period_id)
    
    def update_period_files(self, period_id, file_urls):
        """Update the file_urls field of a period"""
        updates = {"file_urls": file_urls}
        self.period_dao.update_period(period_id, updates)
        print(f"DEBUG: Updated period {period_id} with {len(file_urls)} files")
    
    def get_vector_store_id_for_period(self, period_id):
        period = self.period_dao.get_period_by_id(period_id)
        if not period:
            raise ValueError("Period not found")
        return period['vector_store_id']
    
    def update_period_assistants(self, period_id, update_assistant_id, ltg_assistant_id):
        updates = {
            "update_assistant_id": update_assistant_id,
            "ltg_assistant_id": ltg_assistant_id
        }
        self.period_dao.update_period(period_id, updates)