from services.period.period_management_service import PeriodManagementService


class TeacherService:
    def __init__(self) -> None:
        self._period_mgmt = PeriodManagementService()

    def create_period(self, course, user_id, vector_store_id, file_urls,
                      canvas_course_id=None, canvas_course_name=None):
        return self._period_mgmt.create_period(
            course, user_id, vector_store_id, file_urls,
            canvas_course_id=canvas_course_id,
            canvas_course_name=canvas_course_name,
        )

    def get_periods_by_teacher(self, user_id):
        return self._period_mgmt.get_periods_by_owner(user_id)

    def get_period_by_id(self, period_id):
        return self._period_mgmt.get_period_by_id(period_id)

    def update_period_files(self, period_id, file_urls) -> None:
        self._period_mgmt.update_file_urls(period_id, file_urls)

    def get_vector_store_id_for_period(self, period_id):
        return self._period_mgmt.get_vector_store_id(period_id)
