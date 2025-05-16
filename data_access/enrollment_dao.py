# db/enrollment_dao.py
from data_access.base_dao import BaseDAO
from models.enrollment import Enrollment

class EnrollmentDAO(BaseDAO):
    def __init__(self):
        super().__init__('enrollment')

    def create(self, data: dict):
        enrollment = Enrollment(**data)
        self.table.put_item(Item=enrollment.to_item())

    def get_by_class_id(self, class_id: str):
        return self.table.query(
            KeyConditionExpression=self.key('class_id').eq(class_id)
        )['Items']
