import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from data_access.base_dao import BaseDAO
from data_access.config import DynamoDBConfig
from dotenv import load_dotenv

load_dotenv()

AGGREGATED_METRICS_TABLE = os.getenv("AGGREGATED_METRICS_TABLE_NAME", "aggregated-metrics")


class AggregatedMetricsDAO(BaseDAO):
    def __init__(self):
        config = DynamoDBConfig()
        self.table = config.get_table(AGGREGATED_METRICS_TABLE)

    def add_aggregated_metrics(self, item: Dict[str, Any]) -> None:
        """Create or replace an aggregated metrics record."""
        if "course-week" not in item:
            raise ValueError("Aggregated metrics item must include 'course-week'")

        self.table.put_item(Item=item)

    def get_aggregated_metrics_by_course_week(self, course_week: str) -> Optional[Dict[str, Any]]:
        """Fetch a single aggregated metrics record by its partition key."""
        response = self.table.get_item(Key={"course-week": course_week})
        return response.get("Item")

    def get_skills_by_course_week(self, course_week: str) -> Dict[str, Any]:
        """Return the nested skills map for a course-week, or an empty dict when absent."""
        item = self.get_aggregated_metrics_by_course_week(course_week)
        if not item:
            return {}
        return item.get("skills", {})

    def update_aggregated_metrics(self, course_week: str, updates: Dict[str, Any]) -> None:
        """Update one or more attributes on an aggregated metrics record."""
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
