import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from data_access.base_dao import BaseDAO
from data_access.config import DynamoDBConfig
from dotenv import load_dotenv
from models.aggregated_metrics import AggregatedMetrics, WeekMetrics

load_dotenv()

AGGREGATED_METRICS_TABLE = os.getenv("AGGREGATED_METRICS_TABLE_NAME", "aggregated-metrics")


class AggregatedMetricsDAO(BaseDAO):
    def __init__(self):
        config = DynamoDBConfig()
        self.table = config.get_table(AGGREGATED_METRICS_TABLE)

    def add_aggregated_metrics(self, metrics: AggregatedMetrics) -> None:
        """
        Create or replace an aggregated metrics record from an AggregatedMetrics model.
        """
        item = metrics.to_dynamo_item()
        if "course-week" not in item:
            raise ValueError("Aggregated metrics item must include 'course-week'")

        self.table.put_item(Item=item)

    def get_aggregated_metrics_by_course_week(self, course_week: str) -> Optional[AggregatedMetrics]:
        """
        Fetch a single aggregated metrics record by its partition key and return
        it as an AggregatedMetrics model.
        """
        response = self.table.get_item(Key={"course-week": course_week})
        item = response.get("Item")
        if not item:
            return None
        return AggregatedMetrics.from_dynamo_item(item)

    def get_skills_by_course_week(self, course_week: str) -> List[WeekMetrics]:
        """
        Return the list of WeekMetrics (per-week skill metrics) for a course-week.
        Returns an empty list when the record is absent.
        """
        metrics = self.get_aggregated_metrics_by_course_week(course_week)
        if not metrics:
            return []
        return metrics.weeks

    def update_aggregated_metrics(self, course_week: str, updates: Dict[str, Any]) -> None:
        """
        Update one or more attributes on an aggregated metrics record.

        The `updates` dict should use the raw DynamoDB attribute names, e.g.
        {"Weeks": [...]} to replace the stored weeks structure. A `last_updated_at`
        ISO8601 timestamp is always added.
        """
        if not updates:
            raise ValueError("updates cannot be empty")

        updates["last_updated_at"] = datetime.now(timezone.utc).isoformat()

        update_expr = "SET " + ", ".join(f"#{k} = :{k}" for k in updates)
        expr_attr_names = {f"#{k}": k for k in updates}
        expr_attr_values = {f":{k}": v for k, v in updates.items()}

        self.table.update_item(
            Key={"course-week": course_week},
            UpdateExpression=update_expr,
            ExpressionAttributeNames=expr_attr_names,
            ExpressionAttributeValues=expr_attr_values,
        )

    def delete_aggregated_metrics(self, course_week: str) -> None:
        """Delete an aggregated metrics record by partition key."""
        self.table.delete_item(Key={"course-week": course_week})


AggregatedDAO = AggregatedMetricsDAO
