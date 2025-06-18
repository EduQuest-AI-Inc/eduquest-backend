from data_access.period_dao import PeriodDAO
from models.period import Period
from assistants import create_class

class TeacherService:
    def __init__(self):
        self.period_dao = PeriodDAO()

    def create_period(self, period_id, course, teacher_id):
        existing = self.period_dao.get_period_by_id(period_id)
        if existing:
            raise ValueError("Period ID already exists")
        
        new_class = create_class(class_name=course)
        vector_store_id = new_class.vector_store.id

        #this is the old code
        initial_id = "asst_bmsuvfNCaHJYmqTlnT52AzXE"
        update_id = "asst_oQlKvMpoDPp80zEabjvUiflj"
        ltg_id = "asst_1NnTwxp3tBgFWPp2sMjHU3Or"
        vector_id = new_class.vector_store.id

        new_period = Period(
            period_id=period_id,
            course=course,
            initial_conversation_assistant_id=initial_id,
            update_assistant_id=update_id,
            vector_store_id=vector_id,
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

