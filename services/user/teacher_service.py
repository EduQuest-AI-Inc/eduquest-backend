from data_access.aggregated_metrics_dao import AggregatedMetricsDAO
from data_access.teacher_dao import TeacherDAO


class TeacherService:
    def __init__(self, teacher_dao=None, aggregated_metrics_dao=None, jwt: str | None = None) -> None:
        self.teacher_dao = teacher_dao or TeacherDAO(jwt=jwt)
        self.aggregated_metrics_dao = aggregated_metrics_dao or AggregatedMetricsDAO(jwt=jwt)

    def update_canvas_credentials(self, user_id: str, api_url: str, api_key: str) -> None:
        self.teacher_dao.update_canvas_credentials(user_id, api_url, api_key)

    def get_aggregated_metrics(self, period_id: str):
        return self.aggregated_metrics_dao.get_by_period_id(period_id)
