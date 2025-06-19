from data_access.period_dao import PeriodDAO
from models.period import Period
import os
import assistants
from openai import OpenAI

class TeacherService:
    def __init__(self):
        self.period_dao = PeriodDAO()

    def create_period(self, period_id, course, teacher_id, vector_store_id):
        existing = self.period_dao.get_period_by_id(period_id)
        
        if existing:
            raise ValueError("Period ID already exists")
        
        #call create_class from assistants.py
        # new_class = assistants.create_class(course)
        # vector_store_id = new_class.vector_store.id
        
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
    
    def update_period_assistants(self, period_id, update_assistant_id, ltg_assistant_id):
        updates = {
            "update_assistant_id": update_assistant_id,
            "ltg_assistant_id": ltg_assistant_id
        }
        self.period_dao.update_period(period_id, updates)