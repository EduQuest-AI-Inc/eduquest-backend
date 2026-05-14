from data_access.aggregated_metrics_dao import AggregatedMetricsDAO
from data_access.teacher_dao import TeacherDAO


class TeacherService:
    def __init__(self) -> None:
        self.teacher_dao = TeacherDAO()
        self.aggregated_metrics_dao = AggregatedMetricsDAO()

    def update_canvas_credentials(self, user_id: str, api_url: str, api_key: str) -> None:
        self.teacher_dao.update_canvas_credentials(user_id, api_url, api_key)

    def get_aggregated_metrics(self, period_id: str):
        return self.aggregated_metrics_dao.get_by_period_id(period_id)
